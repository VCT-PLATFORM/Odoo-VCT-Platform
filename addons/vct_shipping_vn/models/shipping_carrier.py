# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class ShippingCarrier(models.Model):
    """Cấu hình nhà vận chuyển VN. Token/shop là credential do người dùng nhập."""
    _name = 'vct.shipping.carrier'
    _description = 'Nhà vận chuyển'
    _order = 'name'

    name = fields.Char('Tên', required=True)
    provider = fields.Selection([
        ('ghn', 'Giao Hàng Nhanh (GHN)'),
        ('ghtk', 'Giao Hàng Tiết Kiệm (GHTK)'),
        ('viettelpost', 'ViettelPost'),
    ], string='Nhà vận chuyển', required=True, default='ghn')
    active = fields.Boolean(default=True)
    token = fields.Char('API Token', password=True)
    shop_id = fields.Char('Shop/Client ID')
    base_url = fields.Char('Base URL', help='Bỏ trống để dùng endpoint mặc định của hãng.')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    shipment_count = fields.Integer(compute='_compute_shipment_count')

    def _compute_shipment_count(self):
        counts = dict(self.env['vct.shipment']._read_group(
            [('carrier_id', 'in', self.ids)], groupby=['carrier_id'], aggregates=['__count']))
        for carrier in self:
            carrier.shipment_count = counts.get(carrier, 0)
