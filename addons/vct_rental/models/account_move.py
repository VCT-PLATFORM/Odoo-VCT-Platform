# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    vct_rental_order_id = fields.Many2one(
        'vct.rental.order', string='Đơn thuê', index=True, ondelete='set null')
