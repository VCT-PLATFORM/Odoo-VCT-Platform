# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_fsm = fields.Boolean(
        string='Dịch vụ hiện trường',
        help="Công việc của dự án này được thực hiện tại chỗ khách hàng: có bấm giờ và xác nhận hoàn thành.")


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # the timer itself lives in timesheet_grid: it is the same clock for every
    # task, field work or not, so there is one implementation, not two
    is_fsm = fields.Boolean(related='project_id.is_fsm', store=True, string='Là công việc hiện trường')
    fsm_done = fields.Boolean(string='Đã hoàn thành tại hiện trường', copy=False, readonly=True)
    fsm_signature = fields.Binary(
        string='Chữ ký khách hàng', copy=False, attachment=True,
        help="Khách ký ngay trên máy của kỹ thuật viên khi nghiệm thu.")
    fsm_signed_by = fields.Char(string='Người ký', copy=False)
    fsm_signed_on = fields.Datetime(string='Ngày ký', copy=False, readonly=True)

    def action_fsm_validate(self):
        """Stop the clock and close the job. The signature is the proof of
        service, so a job cannot be closed without one."""
        for task in self:
            if not task.is_fsm:
                raise UserError(_("Chỉ xác nhận hoàn thành được trên công việc hiện trường."))
            if not task.fsm_signature:
                raise UserError(_(
                    "Cần chữ ký nghiệm thu của khách hàng trước khi hoàn thành công việc."))
        self.action_timer_stop()
        self.write({'fsm_done': True, 'state': '1_done'})

    def write(self, vals):
        if vals.get('fsm_signature'):
            vals.setdefault('fsm_signed_on', fields.Datetime.now())
        return super().write(vals)

    def action_fsm_reopen(self):
        self.write({'fsm_done': False, 'state': '01_in_progress'})

    def action_view_timesheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Giờ công'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id, 'default_project_id': self.project_id.id},
        }
