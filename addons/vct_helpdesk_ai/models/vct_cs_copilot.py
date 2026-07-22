# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models
from odoo.tools import html2plaintext

_TONE = {'polite': 'lịch sự hơn', 'concise': 'ngắn gọn hơn', 'formal': 'trang trọng hơn'}


class VctCsCopilot(models.TransientModel):
    """Trợ lý AI cho nhân viên: gợi ý trả lời / tóm tắt / viết lại. Kết quả hiện cho
    agent xem và sửa trước khi (tuỳ chọn) gửi khách — con người luôn trong vòng lặp."""
    _name = 'vct.cs.copilot'
    _description = 'Copilot AI cho agent'

    ticket_id = fields.Many2one('helpdesk.ticket', required=True, ondelete='cascade')
    mode = fields.Selection([
        ('suggest', 'Gợi ý trả lời'), ('summarize', 'Tóm tắt'), ('rewrite', 'Viết lại'),
    ], required=True)
    tone = fields.Selection([
        ('polite', 'Lịch sự hơn'), ('concise', 'Ngắn gọn hơn'), ('formal', 'Trang trọng hơn'),
    ], default='polite')
    draft = fields.Text('Nội dung cần viết lại')
    result = fields.Text('Kết quả AI')

    def _open_for(self, ticket, mode):
        wiz = self.create({'ticket_id': ticket.id, 'mode': mode})
        if mode in ('suggest', 'summarize'):
            wiz._generate()
        return wiz._action_window()

    def _action_window(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vct.cs.copilot',
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
            'name': dict(self._fields['mode'].selection).get(self.mode),
        }

    def _generate(self):
        self.ensure_one()
        ticket = self.ticket_id
        if self.mode == 'suggest':
            config = self.env['vct.cs.ai.config'].sudo()._get_active()
            kb = config._retrieve_kb('%s %s' % (
                ticket.name, html2plaintext(ticket.description or ''))) if config else []
            kb_txt = '\n---\n'.join('# %s\n%s' % (t, s) for t, s in kb)
            system = ('Bạn là trợ lý cho nhân viên CSKH. Soạn MỘT câu trả lời gợi ý gửi khách: '
                      'lịch sự, ngắn gọn, tiếng Việt. Chỉ dựa thông tin có sẵn, không bịa.')
            user = ('TICKET: %s\n%s\n\nHỘI THOẠI:\n%s\n\nKIẾN THỨC:\n%s\n\nSoạn câu trả lời cho khách.'
                    % (ticket.name, html2plaintext(ticket.description or ''),
                       ticket._conversation_text(), kb_txt))
        elif self.mode == 'summarize':
            system = 'Tóm tắt ngắn gọn (gạch đầu dòng) hội thoại hỗ trợ cho nhân viên, tiếng Việt.'
            user = 'Tóm tắt ticket "%s":\n%s' % (ticket.name, ticket._conversation_text())
        else:  # rewrite
            system = ('Viết lại đoạn dưới cho %s, giữ nguyên ý, tiếng Việt. '
                      'Chỉ trả về đoạn đã viết lại.' % _TONE.get(self.tone, 'lịch sự hơn'))
            user = self.draft or ''
        try:
            self.result = self.env['mail.bot']._run_agent(user, system_prompt=system, use_tools=False)
        except Exception as e:
            self.result = self.env._('(Lỗi gọi AI: %s)', e)

    def action_generate(self):
        self._generate()
        return self._action_window()

    def action_post_reply(self):
        self.ensure_one()
        if self.result:
            self.ticket_id.message_post(
                body=self.result, message_type='comment', subtype_xmlid='mail.mt_comment')
        return {'type': 'ir.actions.act_window_close'}
