# Written for VCT Platform. Not part of Odoo S.A.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestTimesheetReminder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lazy = new_test_user(
            cls.env, 'rem_lazy',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        cls.diligent = new_test_user(
            cls.env, 'rem_diligent',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        cls.emp_lazy = cls.env['hr.employee'].create(
            {'name': 'Lười', 'user_id': cls.lazy.id, 'work_email': 'lazy@example.com'})
        cls.emp_diligent = cls.env['hr.employee'].create(
            {'name': 'Chăm', 'user_id': cls.diligent.id, 'work_email': 'diligent@example.com'})
        cls.project = cls.env['project.project'].create(
            {'name': 'Dự án', 'allow_timesheets': True})
        # a Wednesday, so "last week" is unambiguous
        cls.today = date(2026, 3, 11)

    def _book(self, employee, day):
        return self.env['account.analytic.line'].create({
            'name': 'giờ', 'project_id': self.project.id,
            'employee_id': employee.id, 'unit_amount': 8.0, 'date': day,
        })

    def test_the_period_is_last_monday_to_sunday(self):
        date_from, date_to = self.env['res.users']._timesheet_reminder_period(self.today)
        self.assertEqual(str(date_from), '2026-03-02', "Monday of the previous week")
        self.assertEqual(str(date_to), '2026-03-08', "and its Sunday")

    def test_only_employees_who_booked_nothing_are_chased(self):
        self._book(self.emp_diligent, date(2026, 3, 3))
        late = self.env['res.users']._cron_remind_timesheet_users(self.today)
        self.assertIn(self.emp_lazy, late)
        self.assertNotIn(self.emp_diligent, late, "she filled her timesheet")

    def test_hours_booked_outside_the_period_do_not_count(self):
        self._book(self.emp_diligent, date(2026, 3, 11))   # this week, not last
        late = self.env['res.users']._cron_remind_timesheet_users(self.today)
        self.assertIn(self.emp_diligent, late, "last week is still empty")

    def test_approvers_are_reminded_only_when_something_waits(self):
        approver = new_test_user(
            self.env, 'rem_approver', email='approver@example.com',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_approver')
        self.assertFalse(
            self.env['res.users']._cron_remind_timesheet_approvers(self.today),
            "nothing pending, nobody chased")

        line = self._book(self.emp_diligent, date(2026, 3, 3))
        self.assertIn(approver, self.env['res.users']._cron_remind_timesheet_approvers(self.today))

        line.with_user(approver).action_validate()
        self.assertFalse(
            self.env['res.users']._cron_remind_timesheet_approvers(self.today),
            "once validated there is nothing left to chase")

    def test_the_settings_switches_actually_switch_the_crons(self):
        """hr_timesheet ships these two as upgrade_boolean adverts backed by
        nothing. Here they must drive the real crons."""
        settings = self.env['res.config.settings'].create({})
        user_cron = self.env.ref('timesheet_grid.ir_cron_timesheet_reminder')
        approver_cron = self.env.ref('timesheet_grid.ir_cron_validation_reminder')

        settings.reminder_user_allow = True
        settings.reminder_allow = True
        settings.execute()
        self.assertTrue(user_cron.active)
        self.assertTrue(approver_cron.active)

        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.reminder_user_allow, "the switch must read back on")
        settings.reminder_user_allow = False
        settings.execute()
        self.assertFalse(user_cron.active)
        self.assertTrue(approver_cron.active, "the two switches are independent")
