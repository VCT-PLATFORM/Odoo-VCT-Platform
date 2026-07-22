# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    vct_subscription_id = fields.Many2one(
        'vct.subscription', string='Thuê bao', index=True, ondelete='set null')
