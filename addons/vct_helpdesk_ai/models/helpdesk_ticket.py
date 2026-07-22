# Written for VCT Platform. Not part of Odoo S.A.
from odoo import models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _conversation_text(self, limit=15):
        """Văn bản hội thoại (các comment) theo thứ tự thời gian, để AI đọc."""
        self.ensure_one()
        msgs = self.message_ids.filtered(lambda m: m.message_type == 'comment' and m.body)[:limit]
        return '\n'.join(
            '%s: %s' % (m.author_id.display_name or 'Hệ thống', html2plaintext(m.body))
            for m in reversed(msgs))

    # ---- Copilot cho agent (nội bộ; agent xem trước khi gửi) ----
    def action_ai_suggest_reply(self):
        return self.env['vct.cs.copilot']._open_for(self, 'suggest')

    def action_ai_summarize(self):
        return self.env['vct.cs.copilot']._open_for(self, 'summarize')

    def action_ai_rewrite(self):
        return self.env['vct.cs.copilot']._open_for(self, 'rewrite')

    # ---- AutoQA thủ công ----
    def action_run_qa(self):
        self.ensure_one()
        score = self.env['vct.cs.qa.score']._generate_for(self)
        if not score:
            raise UserError(self.env._('Chưa chấm được (chưa có hội thoại hoặc AI lỗi).'))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vct.cs.qa.score',
            'res_id': score.id, 'view_mode': 'form', 'target': 'new',
        }
