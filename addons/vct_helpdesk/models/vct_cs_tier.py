# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class VctCsTier(models.Model):
    """Hạng khách hàng CSKH (VIP/Thường...). Quyết định mức ưu tiên ticket và —
    qua thẻ SLA — chính sách SLA áp dụng. KHÔNG dựng lại engine SLA: chỉ nâng
    priority / gắn thẻ để `helpdesk.sla` sẵn có tự áp."""
    _name = 'vct.cs.tier'
    _description = 'Hạng khách hàng CSKH'
    _order = 'sequence, id'

    name = fields.Char('Tên hạng', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer('Màu')
    ticket_priority = fields.Selection([
        ('0', 'Thấp'), ('1', 'Trung bình'), ('2', 'Cao'), ('3', 'Khẩn'),
    ], string='Ưu tiên ticket', default='2',
        help='Ticket của KH hạng này được nâng lên mức này khi đang ở mức thấp hơn.')
    sla_tag_id = fields.Many2one(
        'helpdesk.tag', string='Thẻ SLA',
        help='Tự gắn thẻ này lên ticket để chính sách SLA theo thẻ áp dụng.')
    partner_count = fields.Integer('Số KH', compute='_compute_partner_count')

    def _compute_partner_count(self):
        counts = dict(self.env['res.partner']._read_group(
            [('cs_tier_id', 'in', self.ids)], groupby=['cs_tier_id'], aggregates=['__count']))
        for tier in self:
            tier.partner_count = counts.get(tier, 0)   # _read_group m2o → recordset key
