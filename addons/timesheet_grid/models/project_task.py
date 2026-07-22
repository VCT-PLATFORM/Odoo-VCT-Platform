# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    timer_start = fields.Datetime(
        string='Bắt đầu bấm giờ', copy=False, readonly=True,
        help="Thời điểm bắt đầu lượt bấm giờ đang chạy.")
    is_timer_running = fields.Boolean(compute='_compute_is_timer_running')

    @api.depends('timer_start')
    def _compute_is_timer_running(self):
        for task in self:
            task.is_timer_running = bool(task.timer_start)

    def _timesheet_employee(self):
        """The employee whose time is about to be booked, refusing up front
        rather than after the work is done and the elapsed time is lost."""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_(
                "Tài khoản %s chưa gắn với nhân viên nào, nên không ghi nhận được giờ công.",
                self.env.user.display_name))
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
            raise UserError(_(
                "Tài khoản %s chưa có quyền chấm công. Hãy cấp quyền Chấm công cho người dùng này.",
                self.env.user.display_name))
        return employee

    def action_timer_start(self):
        for task in self:
            if not task.project_id.allow_timesheets:
                raise UserError(_("Dự án của công việc này không bật chấm công."))
            if task.timer_start:
                continue
            task._timesheet_employee()
            task.timer_start = fields.Datetime.now()

    def action_timer_stop(self):
        """Close the running timer and book the elapsed time as a timesheet."""
        lines = self.env['account.analytic.line']
        for task in self:
            if not task.timer_start:
                continue
            hours = (fields.Datetime.now() - task.timer_start).total_seconds() / 3600
            task.timer_start = False
            # a timer opened and closed at once is not worth a timesheet line
            if round(hours, 2) <= 0:
                continue
            lines |= self.env['account.analytic.line'].create({
                'name': _('Thời gian làm việc'),
                'task_id': task.id,
                'project_id': task.project_id.id,
                'employee_id': task._timesheet_employee().id,
                'unit_amount': round(hours, 2),
                'date': fields.Date.context_today(task),
            })
        return lines
