# Written for VCT Platform. Not part of Odoo S.A.
from odoo import api, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def message_post(self, **kwargs):
        """Che số nhạy cảm trong nội dung tin trước khi lưu (áp cho cả tin Zalo vào)."""
        if kwargs.get('body'):
            kwargs['body'] = self.env['vct.cs.privacy.config']._mask_text(kwargs['body'])
        return super().message_post(**kwargs)

    @api.model_create_multi
    def create(self, vals_list):
        priv = self.env['vct.cs.privacy.config']
        for vals in vals_list:
            if vals.get('description'):
                vals['description'] = priv._mask_text(vals['description'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('description'):
            vals['description'] = self.env['vct.cs.privacy.config']._mask_text(vals['description'])
        return super().write(vals)
