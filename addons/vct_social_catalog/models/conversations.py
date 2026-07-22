# Written for VCT Platform. Not part of Odoo S.A.
from odoo import models


class ZaloConversation(models.Model):
    _inherit = 'vct.zalo.conversation'

    def _send_text(self, text):
        """Gửi văn bản tới khách qua kênh Zalo."""
        self.ensure_one()
        return self.account_id._send_message(self.zalo_user_id, text)

    def action_share_products(self):
        self.ensure_one()
        return self.env['vct.social.share.wizard']._open_for(self)


class MessengerConversation(models.Model):
    _inherit = 'vct.messenger.conversation'

    def _send_text(self, text):
        """Gửi văn bản tới khách qua kênh Messenger."""
        self.ensure_one()
        return self.account_id._send_message(self.psid, text)

    def action_share_products(self):
        self.ensure_one()
        return self.env['vct.social.share.wizard']._open_for(self)
