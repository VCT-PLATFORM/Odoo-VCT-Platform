# Written for VCT Platform. Not part of Odoo S.A.

from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestIndustryFsm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # booking time needs timesheet rights: a field tech is a timesheet user
        cls.tech = new_test_user(
            cls.env, 'fsm_tech',
            groups='project.group_project_user,hr_timesheet.group_hr_timesheet_user')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Kỹ thuật viên', 'user_id': cls.tech.id,
        })
        cls.fsm_project = cls.env.ref('industry_fsm.fsm_project')
        cls.office_project = cls.env['project.project'].create({
            'name': 'Việc văn phòng', 'is_fsm': False, 'allow_timesheets': True,
        })

    def _task(self, project=None):
        return self.env['project.task'].create({
            'name': 'Sửa máy tại kho',
            'project_id': (project or self.fsm_project).id,
            'user_ids': [(6, 0, self.tech.ids)],
        })

    def test_fsm_flag_follows_the_project(self):
        self.assertTrue(self._task().is_fsm)
        self.assertFalse(self._task(self.office_project).is_fsm)

    SIGNATURE = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

    def test_a_job_cannot_be_closed_without_the_customer_signature(self):
        """The signature is the proof of service: closing without it is what
        makes an invoice unarguable later."""
        task = self._task()
        with self.assertRaises(UserError):
            task.with_user(self.tech).action_fsm_validate()
        self.assertFalse(task.fsm_done)

    def test_signing_stamps_the_date(self):
        task = self._task()
        task.write({'fsm_signature': self.SIGNATURE, 'fsm_signed_by': 'Khách hàng'})
        self.assertTrue(task.fsm_signed_on)

    def test_validate_stops_the_clock_and_closes_the_job(self):
        task = self._task()
        task.write({'fsm_signature': self.SIGNATURE, 'fsm_signed_by': 'Khách hàng'})
        with freeze_time('2026-03-02 08:00:00'):
            task.with_user(self.tech).action_timer_start()
        with freeze_time('2026-03-02 09:00:00'):
            task.with_user(self.tech).action_fsm_validate()
        self.assertFalse(task.is_timer_running, "validating must not leave a timer running")
        self.assertTrue(task.fsm_done)
        self.assertEqual(task.state, '1_done')
        self.assertAlmostEqual(task.effective_hours, 1.0, 2, "the last hour is still booked")

    def test_reopening_clears_the_done_flag(self):
        task = self._task()
        task.write({'fsm_signature': self.SIGNATURE, 'fsm_signed_by': 'Khách hàng'})
        task.with_user(self.tech).action_fsm_validate()
        task.with_user(self.tech).action_fsm_reopen()
        self.assertFalse(task.fsm_done)
        self.assertEqual(task.state, '01_in_progress')

    def test_action_contexts_are_readable_by_the_browser(self):
        """An action's context is evaluated client-side by the JS python
        evaluator, which has no ref(). Using ref() here parses fine on the
        server and blows up with EvalError the moment a user clicks the app.
        The stored context must therefore already be plain literals.
        """
        import ast
        for xmlid in ('industry_fsm.action_fsm_my_tasks',
                      'industry_fsm.action_fsm_all_tasks'):
            context = self.env.ref(xmlid).context
            self.assertNotIn('ref(', context, f"{xmlid}: ref() is server-only")
            # ast.literal_eval accepts literals only — exactly like the JS side
            values = ast.literal_eval(context)
            self.assertEqual(values['default_project_id'],
                             self.env.ref('industry_fsm.fsm_project').id)
