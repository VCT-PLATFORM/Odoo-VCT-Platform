# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, models


class ZaloConversation(models.Model):
    _inherit = 'vct.zalo.conversation'

    def action_create_order(self):
        self.ensure_one()
        return self.env['vct.social.order.wizard']._open_for(
            self.partner_id, _('Zalo: %s', self.partner_id.display_name or self.zalo_user_id))


class MessengerConversation(models.Model):
    _inherit = 'vct.messenger.conversation'

    def action_create_order(self):
        self.ensure_one()
        return self.env['vct.social.order.wizard']._open_for(
            self.partner_id, _('Messenger: %s', self.partner_id.display_name or self.psid))
