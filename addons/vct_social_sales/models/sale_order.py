# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    social_source = fields.Char(
        'Nguồn hội thoại', index=True,
        help='Đơn được chốt từ hội thoại mạng xã hội (Zalo/Messenger).')
