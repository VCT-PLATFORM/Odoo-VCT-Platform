# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _timesheet_reminder_period(self, date=None):
        """Last week: Monday to Sunday, the period people are chased about."""
        date = date or fields.Date.context_today(self)
        monday = date - relativedelta(days=date.weekday(), weeks=1)
        return monday, monday + relativedelta(days=6)

    @api.model
    def _cron_remind_timesheet_users(self, date=None):
        """Chase employees who booked nothing last week."""
        date_from, date_to = self._timesheet_reminder_period(date)
        employees = self.env['hr.employee'].search([('user_id', '!=', False)])
        booked = self.env['account.analytic.line']._read_group(
            [('project_id', '!=', False), ('employee_id', 'in', employees.ids),
             ('date', '>=', date_from), ('date', '<=', date_to)],
            ['employee_id'], ['__count'])
        filled = {employee.id for employee, _count in booked}
        late = employees.filtered(
            lambda e: e.id not in filled and e.work_email
            and e.user_id.has_group('hr_timesheet.group_hr_timesheet_user'))
        template = self.env.ref('timesheet_grid.mail_template_timesheet_reminder',
                                raise_if_not_found=False)
        if template:
            for employee in late:
                template.send_mail(employee.id, force_send=False)
        return late

    @api.model
    def _cron_remind_timesheet_approvers(self, date=None):
        """Tell approvers how much is still waiting on them."""
        date_from, date_to = self._timesheet_reminder_period(date)
        pending = self.env['account.analytic.line'].search_count([
            ('project_id', '!=', False), ('validated', '=', False),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ])
        if not pending:
            return self.browse()
        approvers = self.search([]).filtered(
            lambda u: u.has_group('hr_timesheet.group_hr_timesheet_approver') and u.email)
        template = self.env.ref('timesheet_grid.mail_template_validation_reminder',
                                raise_if_not_found=False)
        if template:
            for approver in approvers:
                template.with_context(pending_count=pending).send_mail(
                    approver.id, force_send=False)
        return approvers
