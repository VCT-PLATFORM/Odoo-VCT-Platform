# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rental_ok = fields.Boolean('Có thể cho thuê')
    rental_price_day = fields.Float('Giá thuê/ngày')
    rental_stock = fields.Integer(
        'Số lượng cho thuê', default=1,
        help='Tổng số đơn vị có thể cho thuê đồng thời (để kiểm trùng lịch).')
