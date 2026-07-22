# Written for VCT Platform. Not part of Odoo S.A.

from datetime import datetime

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestPlanning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(cls.env, 'plan_manager', groups='planning.group_planning_manager')
        cls.worker = new_test_user(cls.env, 'plan_worker', groups='planning.group_planning_user')
        cls.anna = cls.env['hr.employee'].create({'name': 'Anna'})
        cls.bob = cls.env['hr.employee'].create({'name': 'Bob', 'user_id': cls.worker.id})
        cls.role = cls.env.ref('planning.planning_role_default')
        # a Monday, so the week maths below is easy to follow by hand
        cls.monday = datetime(2026, 3, 2, 8, 0)

    def _slot(self, start=None, hours=4, employee='anna', **values):
        start = start or self.monday
        emp = {'anna': self.anna, 'bob': self.bob, None: self.env['hr.employee']}[employee] \
            if isinstance(employee, str) or employee is None else employee
        return self.env['planning.slot'].create({
            'employee_id': emp.id,
            'role_id': self.role.id,
            'start_datetime': start,
            'end_datetime': start + relativedelta(hours=hours),
            **values,
        })

    # --- hours

    def test_allocated_hours_is_the_span(self):
        self.assertAlmostEqual(self._slot(hours=8).allocated_hours, 8.0, 2)
        self.assertAlmostEqual(self._slot(hours=1).allocated_hours, 1.0, 2)

    @mute_logger('odoo.sql_db')
    def test_a_shift_cannot_end_before_it_starts(self):
        with self.assertRaises(IntegrityError):
            self.env['planning.slot'].create({
                'employee_id': self.anna.id,
                'start_datetime': self.monday,
                'end_datetime': self.monday - relativedelta(hours=1),
            })

    # --- conflicts

    def test_overlapping_shifts_are_flagged(self):
        first = self._slot(hours=8)                                    # 08:00-16:00
        second = self._slot(start=self.monday + relativedelta(hours=4))  # 12:00-16:00
        self.assertEqual(first.conflict_count, 1)
        self.assertEqual(second.conflict_count, 1)

    def test_back_to_back_shifts_are_not_a_conflict(self):
        first = self._slot(hours=4)                                     # 08:00-12:00
        second = self._slot(start=self.monday + relativedelta(hours=4))  # 12:00-16:00
        self.assertEqual(first.conflict_count, 0, "ending as the next begins is fine")
        self.assertEqual(second.conflict_count, 0)

    def test_different_employees_never_conflict(self):
        anna = self._slot(hours=8)
        bob = self._slot(hours=8, employee='bob')
        self.assertEqual(anna.conflict_count, 0)
        self.assertEqual(bob.conflict_count, 0)

    def test_open_shifts_never_conflict(self):
        self._slot(hours=8)
        open_slot = self._slot(hours=8, employee=None)
        self.assertEqual(open_slot.conflict_count, 0, "nobody is booked on an open shift")

    def test_conflict_action_lists_the_other_shift(self):
        first = self._slot(hours=8)
        second = self._slot(start=self.monday + relativedelta(hours=4))
        action = first.action_view_conflicts()
        self.assertEqual(action['domain'], [('id', 'in', second.ids)])

    # --- open shifts

    def test_an_employee_can_take_an_open_shift(self):
        slot = self._slot(employee=None)
        self.assertTrue(slot.is_unassigned)
        slot.with_user(self.worker).action_assign_to_me()
        self.assertEqual(slot.employee_id, self.bob)
        self.assertFalse(slot.is_unassigned)

    def test_taking_someone_elses_shift_is_refused(self):
        slot = self._slot(employee='anna')
        with self.assertRaises(UserError):
            slot.with_user(self.worker).action_assign_to_me()

    # --- publishing

    def test_publishing_an_open_shift_is_refused(self):
        slot = self._slot(employee=None)
        with self.assertRaises(UserError):
            slot.action_publish()

    def test_publish_and_unpublish(self):
        slot = self._slot()
        self.assertEqual(slot.state, 'draft')
        slot.action_publish()
        self.assertEqual(slot.state, 'published')
        slot.action_unpublish()
        self.assertEqual(slot.state, 'draft')

    def test_employees_only_see_published_and_open_shifts(self):
        draft = self._slot(employee='bob')
        published = self._slot(start=self.monday + relativedelta(days=1), employee='bob')
        published.action_publish()
        open_slot = self._slot(start=self.monday + relativedelta(days=2), employee=None)

        visible = self.env['planning.slot'].with_user(self.worker).search([])
        self.assertIn(published, visible)
        self.assertIn(open_slot, visible, "an open shift is up for grabs, so it must be visible")
        self.assertNotIn(draft, visible, "a draft roster is not announced yet")

    def test_an_employee_cannot_create_shifts(self):
        with self.assertRaises(AccessError):
            self.env['planning.slot'].with_user(self.worker).create({
                'employee_id': self.bob.id,
                'start_datetime': self.monday,
                'end_datetime': self.monday + relativedelta(hours=4),
            })

    # --- copy / repeat

    def test_copy_previous_week_shifts_everything_by_seven_days(self):
        self._slot(hours=8)
        self._slot(start=self.monday + relativedelta(days=1), hours=6, employee='bob')
        copies = self.env['planning.slot'].action_copy_previous_week(
            date_start=self.monday + relativedelta(days=7))
        self.assertEqual(len(copies), 2)
        self.assertEqual(sorted(copies.mapped('start_datetime')), [
            self.monday + relativedelta(days=7),
            self.monday + relativedelta(days=8),
        ])
        self.assertTrue(all(c.state == 'draft' for c in copies), "copies start as drafts")
        self.assertAlmostEqual(sum(copies.mapped('allocated_hours')), 14.0, 2)

    def test_copy_previous_week_refuses_to_double_book(self):
        self._slot(hours=8)
        self._slot(start=self.monday + relativedelta(days=7))
        with self.assertRaises(UserError):
            self.env['planning.slot'].action_copy_previous_week(
                date_start=self.monday + relativedelta(days=7))

    def test_copy_previous_week_needs_something_to_copy(self):
        with self.assertRaises(UserError):
            self.env['planning.slot'].action_copy_previous_week(
                date_start=self.monday + relativedelta(days=7))

    def test_repeat_weekly_creates_one_shift_per_week(self):
        slot = self._slot(hours=8)
        repeats = slot.action_repeat_weekly(weeks=3)
        self.assertEqual(len(repeats), 3)
        self.assertEqual(sorted(repeats.mapped('start_datetime')), [
            self.monday + relativedelta(weeks=1),
            self.monday + relativedelta(weeks=2),
            self.monday + relativedelta(weeks=3),
        ])
        self.assertTrue(all(r.employee_id == self.anna for r in repeats))

    def test_repeat_weekly_rejects_a_meaningless_count(self):
        with self.assertRaises(UserError):
            self._slot().action_repeat_weekly(weeks=0)

    # --- the UI must actually be able to reach the features above

    def test_copy_previous_week_is_reachable_from_a_menu(self):
        """It was written, tested and advertised, but nothing called it."""
        action = self.env.ref('planning.action_copy_previous_week')
        self.assertEqual(action.model_id.model, 'planning.slot')
        menu = self.env.ref('planning.menu_planning_copy_week')
        self.assertEqual(menu.action, action)

    def test_repeat_weekly_is_reachable_from_the_form(self):
        view = self.env.ref('planning.planning_slot_view_form')
        self.assertIn('action_repeat_weekly_button', view.arch)

    def test_repeat_button_uses_the_configured_number_of_weeks(self):
        slot = self._slot(hours=8)
        slot.repeat_weeks = 2
        self.assertEqual(len(slot.action_repeat_weekly_button()), 2)
