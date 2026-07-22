# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    repair_ids = fields.One2many('repair.order', 'ticket_id', string='Lệnh sửa chữa')
    repair_count = fields.Integer(compute='_compute_repair_count', string='Số lệnh sửa chữa')

    @api.depends('repair_ids')
    def _compute_repair_count(self):
        counts = dict(self.env['repair.order']._read_group(
            [('ticket_id', 'in', self.ids)], ['ticket_id'], ['__count']))
        for ticket in self:
            ticket.repair_count = counts.get(ticket, 0)

    def action_create_repair(self):
        """Open a repair order prefilled from the ticket."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lệnh sửa chữa'),
            'res_model': 'repair.order',
            'view_mode': 'form',
            'context': {
                'default_ticket_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_internal_notes': self.name,
            },
        }

    def action_view_repairs(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Lệnh sửa chữa'),
            'res_model': 'repair.order',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id, 'default_partner_id': self.partner_id.id},
        }
        if self.repair_count == 1:
            action.update(view_mode='form', res_id=self.repair_ids.id)
        else:
            action.update(view_mode='list,form')
        return action


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Phiếu hỗ trợ', index='btree_not_null',
        help="Phiếu hỗ trợ đã phát sinh ra lệnh sửa chữa này.")
