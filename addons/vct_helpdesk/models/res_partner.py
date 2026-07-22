# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cs_tier_id = fields.Many2one(
        'vct.cs.tier', string='Hạng CSKH', tracking=True, index=True,
        help='Hạng khách hàng cho chăm sóc — chi phối ưu tiên & SLA của ticket.')
