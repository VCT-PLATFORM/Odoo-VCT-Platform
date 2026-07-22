# Written for VCT Platform. Not part of Odoo S.A.

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestTimesheetValidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker = new_test_user(
            cls.env, 'ts_worker',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        cls.approver = new_test_user(
            cls.env, 'ts_approver',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_approver')
        cls.employee = cls.env['hr.employee'].create({'name': 'Thợ', 'user_id': cls.worker.id})
        cls.project = cls.env['project.project'].create({
            'name': 'Dự án', 'allow_timesheets': True,
        })
        cls.task = cls.env['project.task'].create({
            'name': 'Việc', 'project_id': cls.project.id,
        })

    def _line(self, hours=2.0):
        return self.env['account.analytic.line'].create({
            'name': 'giờ công',
            'project_id': self.project.id,
            'task_id': self.task.id,
            'employee_id': self.employee.id,
            'unit_amount': hours,
            'date': fields.Date.today(),
        })

    def test_a_new_line_is_not_validated(self):
        self.assertFalse(self._line().validated)

    def test_an_approver_validates_and_stamps_who_and_when(self):
        line = self._line()
        line.with_user(self.approver).action_validate()
        self.assertTrue(line.validated)
        self.assertEqual(line.validated_by_id, self.approver)
        self.assertTrue(line.validated_date)

    def test_a_worker_cannot_validate_their_own_hours(self):
        line = self._line()
        with self.assertRaises(UserError):
            line.with_user(self.worker).action_validate()
        self.assertFalse(line.validated)

    def test_a_validated_line_is_locked_for_the_worker(self):
        line = self._line()
        line.with_user(self.approver).action_validate()
        with self.assertRaises(UserError):
            line.with_user(self.worker).unit_amount = 99
        with self.assertRaises(UserError):
            line.with_user(self.worker).unlink()
        self.assertAlmostEqual(line.unit_amount, 2.0, 2, "the hours must be untouched")

    def test_an_unvalidated_line_stays_editable(self):
        line = self._line()
        line.with_user(self.worker).unit_amount = 3.0
        self.assertAlmostEqual(line.unit_amount, 3.0, 2)

    def test_an_approver_can_still_correct_a_validated_line(self):
        line = self._line()
        line.with_user(self.approver).action_validate()
        line.with_user(self.approver).unit_amount = 5.0
        self.assertAlmostEqual(line.unit_amount, 5.0, 2)

    def test_invalidating_unlocks_the_line_again(self):
        line = self._line()
        line.with_user(self.approver).action_validate()
        line.with_user(self.approver).action_invalidate()
        self.assertFalse(line.validated)
        self.assertFalse(line.validated_by_id)
        line.with_user(self.worker).unit_amount = 4.0
        self.assertAlmostEqual(line.unit_amount, 4.0, 2, "unlocked means editable again")

    def test_a_worker_cannot_invalidate(self):
        line = self._line()
        line.with_user(self.approver).action_validate()
        with self.assertRaises(UserError):
            line.with_user(self.worker).action_invalidate()
        self.assertTrue(line.validated, "the lock must hold")

    def test_a_worker_cannot_unlock_a_line_by_writing_the_flag(self):
        """The lock must not be openable by the very field that defines it."""
        line = self._line()
        line.with_user(self.approver).action_validate()
        with self.assertRaises(Exception):
            line.with_user(self.worker).write({'validated': False, 'unit_amount': 99})
        self.assertAlmostEqual(line.unit_amount, 2.0, 2)

    def test_plain_analytic_lines_are_not_timesheets(self):
        """An accounting analytic line has no project: the approval flow must
        leave it alone."""
        plan = self.env['account.analytic.plan'].create({'name': 'Kế hoạch'})
        account = self.env['account.analytic.account'].create({
            'name': 'Tài khoản', 'plan_id': plan.id,
        })
        line = self.env['account.analytic.line'].create({
            'name': 'chi phí', 'account_id': account.id, 'amount': -10,
        })
        with self.assertRaises(UserError):
            line.with_user(self.approver).action_validate()
