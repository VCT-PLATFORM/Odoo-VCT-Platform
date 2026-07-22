# Written for VCT Platform. Not part of Odoo S.A.

from datetime import datetime

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestTimesheetTimer(TransactionCase):
    """The timer lives here rather than in industry_fsm: the same clock serves
    every task, so it is tested once."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker = new_test_user(
            cls.env, 'timer_worker',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        cls.employee = cls.env['hr.employee'].create({'name': 'Thợ', 'user_id': cls.worker.id})
        cls.project = cls.env['project.project'].create(
            {'name': 'Dự án', 'allow_timesheets': True})
        cls.no_ts_project = cls.env['project.project'].create(
            {'name': 'Không chấm công', 'allow_timesheets': False})

    def _task(self, project=None):
        return self.env['project.task'].create({
            'name': 'Việc', 'project_id': (project or self.project).id,
        })

    def test_timer_needs_a_project_that_allows_timesheets(self):
        with self.assertRaises(UserError):
            self._task(self.no_ts_project).with_user(self.worker).action_timer_start()

    def test_timer_books_the_elapsed_time(self):
        task = self._task()
        with freeze_time('2026-03-02 08:00:00'):
            task.with_user(self.worker).action_timer_start()
            self.assertTrue(task.is_timer_running)
        with freeze_time('2026-03-02 10:30:00'):
            lines = task.with_user(self.worker).action_timer_stop()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines.unit_amount, 2.5, 2, "08:00 to 10:30 is 2.5 hours")
        self.assertEqual(lines.employee_id, self.employee)
        self.assertFalse(task.is_timer_running)
        self.assertAlmostEqual(task.effective_hours, 2.5, 2)

    def test_starting_twice_does_not_reset_the_clock(self):
        task = self._task()
        with freeze_time('2026-03-02 08:00:00'):
            task.with_user(self.worker).action_timer_start()
        with freeze_time('2026-03-02 09:00:00'):
            task.with_user(self.worker).action_timer_start()
            self.assertEqual(str(task.timer_start), '2026-03-02 08:00:00',
                             "a second start must not lose the first hour")

    def test_an_instant_timer_books_nothing(self):
        task = self._task()
        with freeze_time('2026-03-02 08:00:00'):
            task.with_user(self.worker).action_timer_start()
            self.assertFalse(task.with_user(self.worker).action_timer_stop())

    def test_stopping_an_idle_timer_is_harmless(self):
        self.assertFalse(self._task().with_user(self.worker).action_timer_stop())

    def test_a_user_without_an_employee_cannot_book_time(self):
        stranger = new_test_user(
            self.env, 'timer_stranger',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        with self.assertRaises(UserError):
            self._task().with_user(stranger).action_timer_start()

    def test_a_user_without_timesheet_rights_is_told_up_front(self):
        """The timer must refuse before the work, not after the time is spent."""
        no_rights = new_test_user(self.env, 'timer_norights', groups='project.group_project_user')
        self.env['hr.employee'].create({'name': 'Không quyền', 'user_id': no_rights.id})
        task = self._task()
        with self.assertRaises(UserError):
            task.with_user(no_rights).action_timer_start()
        self.assertFalse(task.timer_start, "the clock must not be left running")

    def test_two_sessions_accumulate(self):
        task = self._task()
        for start, stop in [('2026-03-02 08:00:00', '2026-03-02 09:00:00'),
                            ('2026-03-03 08:00:00', '2026-03-03 08:30:00')]:
            with freeze_time(start):
                task.with_user(self.worker).action_timer_start()
            with freeze_time(stop):
                task.with_user(self.worker).action_timer_stop()
        self.assertAlmostEqual(task.effective_hours, 1.5, 2, "1h + 0.5h")

    def test_a_booked_line_can_still_be_validated(self):
        """The timer and the approval flow are the same module: a timed line
        must go through validation like any other."""
        task = self._task()
        approver = new_test_user(
            self.env, 'timer_approver',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_approver')
        with freeze_time('2026-03-02 08:00:00'):
            task.with_user(self.worker).action_timer_start()
        with freeze_time('2026-03-02 09:00:00'):
            line = task.with_user(self.worker).action_timer_stop()
        line.with_user(approver).action_validate()
        self.assertTrue(line.validated)
        with self.assertRaises(UserError):
            line.with_user(self.worker).unit_amount = 99
