# Written for VCT Platform. Not part of Odoo S.A.
import logging

from odoo import models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def message_post(self, **kwargs):
        """Agent trả lời công khai → đẩy ra Messenger. Bỏ qua tin do webhook tạo
        (messenger_inbound), ghi chú nội bộ, và tin hệ thống."""
        message = super().message_post(**kwargs)
        if self.env.context.get('messenger_inbound'):
            return message
        try:
            comment_subtype = self.env.ref('mail.mt_comment')
            if (message.message_type == 'comment'
                    and message.subtype_id == comment_subtype and message.body):
                conv = self.env['vct.messenger.conversation'].sudo().search(
                    [('ticket_id', '=', self.id), ('state', '!=', 'closed')], limit=1)
                if conv:
                    conv.account_id._send_message(conv.psid, html2plaintext(message.body))
        except Exception:
            _logger.exception('Messenger: đẩy tin ra thất bại cho ticket %s', self.id)
        return message
