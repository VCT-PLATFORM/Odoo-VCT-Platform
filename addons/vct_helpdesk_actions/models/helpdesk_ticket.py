# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    """Từ ticket tạo việc kỹ thuật viên (FSM) + phiếu hoàn tiền/đổi trả. Theo pattern
    native của helpdesk_repair: mở form điền sẵn → người xem & lưu = xác nhận
    (không tự động ghi). Phiếu sửa chữa/bảo hành dùng nút `action_create_repair`
    có sẵn của helpdesk_repair."""
    _inherit = 'helpdesk.ticket'

    fsm_task_ids = fields.One2many('project.task', 'helpdesk_ticket_id', string='Việc kỹ thuật viên')
    fsm_task_count = fields.Integer(compute='_compute_fsm_task_count')

    @api.depends('fsm_task_ids')
    def _compute_fsm_task_count(self):
        counts = dict(self.env['project.task']._read_group(
            [('helpdesk_ticket_id', 'in', self.ids)], ['helpdesk_ticket_id'], ['__count']))
        for ticket in self:
            ticket.fsm_task_count = counts.get(ticket, 0)

    def action_create_fsm_task(self):
        """Mở form việc kỹ thuật viên (FSM) điền sẵn từ ticket."""
        self.ensure_one()
        project = self.env['project.project'].search([('is_fsm', '=', True)], limit=1)
        if not project:
            raise UserError(_('Chưa có dự án "Dịch vụ hiện trường" (FSM) để tạo việc.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Việc kỹ thuật viên'),
            'res_model': 'project.task', 'view_mode': 'form',
            'context': {
                'default_project_id': project.id,
                'default_partner_id': self.partner_id.id,
                'default_name': _('KTV: %s', self.name),
                'default_helpdesk_ticket_id': self.id,
            },
        }

    def action_view_fsm_tasks(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window', 'name': _('Việc kỹ thuật viên'),
            'res_model': 'project.task', 'domain': [('helpdesk_ticket_id', '=', self.id)],
            'context': {'default_helpdesk_ticket_id': self.id, 'default_partner_id': self.partner_id.id},
        }
        if self.fsm_task_count == 1:
            action.update(view_mode='form', res_id=self.fsm_task_ids.id)
        else:
            action.update(view_mode='list,form')
        return action

    def action_create_refund(self):
        """Mở phiếu hoàn tiền/đổi trả (credit note) điền sẵn từ ticket."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Ticket chưa có khách hàng để lập phiếu hoàn.'))
        ref = (_('Hoàn cho HĐ %(inv)s (ticket %(t)s)', inv=self.invoice_id.name, t=self.name)
               if self.invoice_id else _('Đổi trả/hoàn từ ticket %s', self.name))
        return {
            'type': 'ir.actions.act_window', 'name': _('Hoàn tiền / Đổi trả'),
            'res_model': 'account.move', 'view_mode': 'form',
            'context': {
                'default_move_type': 'out_refund',
                'default_partner_id': self.partner_id.id,
                'default_ref': ref,
                'default_invoice_origin': self.invoice_id.name or False,
            },
        }
