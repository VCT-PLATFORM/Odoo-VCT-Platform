# Written for VCT Platform. Not part of Odoo S.A.
from odoo import models


class VctZaloConversation(models.Model):
    _inherit = 'vct.zalo.conversation'

    def _get_or_create(self, account, zalo_user_id, display_name=None):
        """Hội thoại mới → để 'bot' xử lý khi AI autoreply đang bật (mặc định Phase 2
        là 'human'). Hội thoại cũ giữ nguyên trạng thái (đã escalate thì vẫn 'human')."""
        existed = self.search(
            [('account_id', '=', account.id), ('zalo_user_id', '=', zalo_user_id)], limit=1)
        conv = super()._get_or_create(account, zalo_user_id, display_name)
        if not existed:
            config = self.env['vct.cs.ai.config'].sudo()._get_active()
            if config and config.zalo_autoreply:
                conv.state = 'bot'
        return conv
