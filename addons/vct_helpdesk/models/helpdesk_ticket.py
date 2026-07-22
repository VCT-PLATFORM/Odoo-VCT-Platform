# Written for VCT Platform. Not part of Odoo S.A.
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    """Biến ticket thành điểm nhìn ERP 360°: gắn nghiệp vụ (đơn/hoá đơn/bảo hành),
    tổng hợp công nợ & lịch sử KH, ticket cha–con. Tái dùng SLA/CSAT/team sẵn có."""
    _inherit = 'helpdesk.ticket'

    # KH cấp công ty — mọi tổng hợp 360 gom theo đây để bắt cả liên hệ con
    commercial_partner_id = fields.Many2one(
        'res.partner', related='partner_id.commercial_partner_id',
        string='KH (công ty)', store=True, index=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id')
    cs_tier_id = fields.Many2one(
        related='commercial_partner_id.cs_tier_id', string='Hạng CSKH',
        store=True, index=True)

    # ---- Gắn nghiệp vụ ERP (repair_ids đã có sẵn từ helpdesk_repair) ----
    sale_order_id = fields.Many2one(
        'sale.order', string='Đơn hàng liên quan',
        domain="[('partner_id', 'child_of', commercial_partner_id)]")
    invoice_id = fields.Many2one(
        'account.move', string='Hoá đơn liên quan',
        domain="[('move_type', 'in', ('out_invoice', 'out_refund')),"
               " ('partner_id', 'child_of', commercial_partner_id)]")

    # ---- Ticket cha–con + liên quan ----
    parent_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket cha', index=True, ondelete='set null')
    child_ids = fields.One2many('helpdesk.ticket', 'parent_id', string='Ticket con')
    child_count = fields.Integer(compute='_compute_child_count')
    related_ticket_ids = fields.Many2many(
        'helpdesk.ticket', 'vct_helpdesk_ticket_rel', 'ticket_id', 'related_id',
        string='Ticket liên quan')

    # ---- 360°: tổng hợp KH (computed, không lưu → luôn tươi, không nhân bản) ----
    partner_due_amount = fields.Monetary(
        string='Công nợ phải thu', compute='_compute_partner_360',
        currency_field='company_currency_id')
    partner_sale_count = fields.Integer('Số đơn hàng', compute='_compute_partner_360')
    partner_sale_total = fields.Monetary(
        string='Tổng giá trị đơn', compute='_compute_partner_360',
        currency_field='company_currency_id')
    partner_last_order_id = fields.Many2one(
        'sale.order', string='Đơn gần nhất', compute='_compute_partner_360')
    partner_ticket_count = fields.Integer('Ticket khác của KH', compute='_compute_partner_360')
    partner_warranty_count = fields.Integer('Lượt bảo hành/sửa chữa', compute='_compute_partner_360')

    @api.depends('child_ids')
    def _compute_child_count(self):
        for ticket in self:
            ticket.child_count = len(ticket.child_ids)

    @api.depends('commercial_partner_id')
    def _compute_partner_360(self):
        Sale = self.env['sale.order']
        Repair = self.env['repair.order']
        for ticket in self:
            cp = ticket.commercial_partner_id
            if not cp:
                ticket.partner_due_amount = 0.0
                ticket.partner_sale_count = 0
                ticket.partner_sale_total = 0.0
                ticket.partner_last_order_id = False
                ticket.partner_ticket_count = 0
                ticket.partner_warranty_count = 0
                continue
            orders = Sale.search([('partner_id', 'child_of', cp.id)], order='date_order desc')
            ticket.partner_sale_count = len(orders)
            ticket.partner_sale_total = sum(orders.mapped('amount_total'))
            ticket.partner_last_order_id = orders[:1].id
            ticket.partner_due_amount = cp.credit
            # _origin.id: bản ghi chưa lưu có NewId → loại self an toàn
            ticket.partner_ticket_count = self.search_count([
                ('partner_id', 'child_of', cp.id), ('id', '!=', ticket._origin.id or 0)])
            ticket.partner_warranty_count = Repair.search_count([('partner_id', 'child_of', cp.id)])

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket._apply_cs_tier()
        return tickets

    def _apply_cs_tier(self):
        """KH có hạng → nâng ưu tiên (nếu đang thấp) + gắn thẻ SLA. Không đè mức
        ưu tiên cao đã đặt tay."""
        self.ensure_one()
        tier = self.cs_tier_id
        if not tier:
            return
        vals = {}
        if tier.ticket_priority and (self.priority or '0') < tier.ticket_priority:
            vals['priority'] = tier.ticket_priority
        if tier.sla_tag_id and tier.sla_tag_id not in self.tag_ids:
            vals['tag_ids'] = [(4, tier.sla_tag_id.id)]
        if vals:
            self.write(vals)

    def action_open_child_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Ticket con'),
            'res_model': 'helpdesk.ticket', 'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id, 'default_partner_id': self.partner_id.id},
        }

    def action_open_partner_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Ticket của khách'),
            'res_model': 'helpdesk.ticket', 'view_mode': 'list,form',
            'domain': [('partner_id', 'child_of', self.commercial_partner_id.id)],
        }
