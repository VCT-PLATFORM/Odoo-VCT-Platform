# Written for VCT Platform. Not part of Odoo S.A.
import logging

from odoo import models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def message_post(self, **kwargs):
        """Agent trả lời công khai trong chatter → đẩy ra Zalo. Bỏ qua:
        - tin do webhook Zalo tạo (context zalo_inbound) → tránh dội ngược;
        - ghi chú nội bộ (subtype khác mt_comment);
        - tin hệ thống (message_type != comment)."""
        message = super().message_post(**kwargs)
        if self.env.context.get('zalo_inbound'):
            return message
        try:
            comment_subtype = self.env.ref('mail.mt_comment')
            if (message.message_type == 'comment'
                    and message.subtype_id == comment_subtype
                    and message.body):
                conv = self.env['vct.zalo.conversation'].sudo().search(
                    [('ticket_id', '=', self.id), ('state', '!=', 'closed')], limit=1)
                if conv:
                    conv.account_id._send_message(
                        conv.zalo_user_id, html2plaintext(message.body))
        except Exception:
            # Không để lỗi Zalo làm hỏng việc đăng tin trong Odoo
            _logger.exception('Zalo: đẩy tin ra thất bại cho ticket %s', self.id)
        return message
