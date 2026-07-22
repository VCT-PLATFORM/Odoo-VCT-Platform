# Written for VCT Platform. Not part of Odoo S.A.

from odoo import models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def website_form_input_filter(self, request, values):
        """Tickets filed from a public form: trust nothing the visitor sends
        beyond the whitelisted fields, and match them to a partner by email the
        same way the mail gateway does."""
        values.setdefault('name', self.env._('Yêu cầu từ website'))
        email = values.get('partner_email')
        if email and not values.get('partner_id'):
            partner = self.env['res.partner'].sudo().search(
                [('email_normalized', '=', email.strip().lower())], limit=1)
            if partner:
                values['partner_id'] = partner.id
        return values
