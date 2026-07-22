# Written for VCT Platform. Not part of Odoo S.A.
from odoo import models


class VctZaloAccount(models.Model):
    _inherit = 'vct.zalo.account'

    def _handle_inbound(self, zalo_user_id, text, display_name=None):
        """Sau khi Phase 2 đã tạo ticket + ghi tin vào, nếu AI bật và hội thoại
        đang ở trạng thái 'bot' → AI trả lời hoặc tự chuyển nhân viên."""
        ticket = super()._handle_inbound(zalo_user_id, text, display_name)
        config = self.env['vct.cs.ai.config'].sudo()._get_active()
        if not config or not config.zalo_autoreply:
            return ticket
        conv = self.env['vct.zalo.conversation'].sudo().search(
            [('account_id', '=', self.id), ('zalo_user_id', '=', zalo_user_id)], limit=1)
        if not conv or conv.state != 'bot':   # đã chuyển người → AI im lặng
            return ticket

        answer, escalate = config._answer(conv.partner_id, text)
        self.env['vct.cs.ai.log'].sudo().create({
            'config_id': config.id, 'partner_id': conv.partner_id.id, 'ticket_id': ticket.id,
            'question': text or '', 'answer': answer, 'escalated': escalate})

        if escalate:
            conv.state = 'human'
            ticket.message_post(
                body=self.env._('🤖→👤 AI chuyển cho nhân viên (không đủ thông tin / ngoài phạm vi).'),
                message_type='comment', subtype_xmlid='mail.mt_note')
        else:
            self._send_message(conv.zalo_user_id, answer)
            # ghi vào chatter, zalo_inbound=True để override Phase 2 KHÔNG gửi lặp
            ticket.with_context(zalo_inbound=True).message_post(
                body='🤖 ' + (answer or ''),
                message_type='comment', subtype_xmlid='mail.mt_comment')
        return ticket
