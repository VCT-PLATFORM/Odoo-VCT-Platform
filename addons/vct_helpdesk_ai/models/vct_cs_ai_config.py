# Written for VCT Platform. Not part of Odoo S.A.
import logging
import re

from odoo import api, fields, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Model tự trả về đúng dòng này khi không đủ tự tin → chuyển nhân viên.
ESCALATE = '<ESCALATE>'


class VctCsAiConfig(models.Model):
    """Bộ não AI CSKH. Cách an toàn: KHÔNG đưa tool ERP cho model. Pre-fetch đúng
    dữ liệu của partner đã xác thực + RAG từ Knowledge Base, nhồi vào prompt, gọi
    LLM `use_tools=False`. Model không có tool nào để tra dữ liệu KH khác."""
    _name = 'vct.cs.ai.config'
    _description = 'Cấu hình AI CSKH'

    name = fields.Char('Tên', required=True, default='Cấu hình AI CSKH')
    active = fields.Boolean(default=True)
    zalo_autoreply = fields.Boolean(
        'AI tự trả lời trên Zalo', default=False,
        help='Bật thì AI trả lời khách trên Zalo; dưới ngưỡng tự tin sẽ tự chuyển nhân viên.')
    kb_root_article_id = fields.Many2one(
        'knowledge.article', string='Gốc Knowledge Base',
        help='Giới hạn RAG trong nhánh bài viết này. Trống = tìm mọi bài.')
    max_kb = fields.Integer('Số đoạn KB tối đa', default=3)
    include_partner_context = fields.Boolean(
        'Kèm dữ liệu khách (đơn/công nợ/bảo hành)', default=True)
    policy_text = fields.Text(
        'Chính sách/Hướng dẫn thêm cho AI',
        help='Ví dụ: giờ làm việc, chính sách đổi trả, không hứa giảm giá...')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    log_count = fields.Integer(compute='_compute_log_count')

    @api.model
    def _get_active(self):
        return self.search([('active', '=', True)], limit=1)

    def _compute_log_count(self):
        counts = dict(self.env['vct.cs.ai.log']._read_group(
            [('config_id', 'in', self.ids)], groupby=['config_id'], aggregates=['__count']))
        for cfg in self:
            cfg.log_count = counts.get(cfg, 0)

    # ---- RAG: lấy đoạn Knowledge Base liên quan ----
    def _retrieve_kb(self, question):
        self.ensure_one()
        words = [w for w in re.split(r'\W+', question or '') if len(w) > 3]
        if not words:
            return []
        leaves = []
        for w in words:
            leaves += [('name', 'ilike', w), ('body', 'ilike', w)]
        domain = ['|'] * (len(leaves) - 1) + leaves     # khớp bất kỳ từ khoá (name/body)
        if self.kb_root_article_id:
            domain = ['&', ('id', 'child_of', self.kb_root_article_id.id)] + domain
        articles = self.env['knowledge.article'].sudo().search(domain, limit=self.max_kb or 3)
        return [(a.name, html2plaintext(a.body or '')[:600]) for a in articles]

    # ---- Ngữ cảnh KH: CHỈ dữ liệu của partner đã xác thực ----
    def _partner_context(self, partner):
        if not partner:
            return ''
        cp = partner.commercial_partner_id
        parts = ['Khách hàng: %s' % cp.display_name, 'Công nợ phải thu: %s' % cp.credit]
        orders = self.env['sale.order'].sudo().search(
            [('partner_id', 'child_of', cp.id)], order='date_order desc', limit=5)
        if orders:
            parts.append('Đơn hàng gần đây:\n' + '\n'.join(
                '- %s: trạng thái %s, giao hàng %s, tổng %s, ngày %s' % (
                    o.name, o.state, o.delivery_status or 'n/a', o.amount_total,
                    o.date_order and o.date_order.date() or '?') for o in orders))
        repairs = self.env['repair.order'].sudo().search(
            [('partner_id', 'child_of', cp.id)], order='id desc', limit=5)
        if repairs:
            parts.append('Bảo hành/sửa chữa:\n' + '\n'.join(
                '- %s: %s' % (r.name, r.state) for r in repairs))
        return '\n'.join(parts)

    def _build_system_prompt(self, partner, kb_snippets):
        self.ensure_one()
        parts = [
            'Bạn là trợ lý chăm sóc khách hàng. Trả lời NGẮN GỌN, lịch sự, bằng tiếng Việt.',
            'CHỈ dựa vào NGỮ CẢNH bên dưới (Knowledge Base + dữ liệu khách). TUYỆT ĐỐI không bịa thông tin.',
            'Nếu không đủ thông tin, câu hỏi ngoài phạm vi, hoặc khách muốn gặp người thật, '
            'hãy trả lời đúng một dòng duy nhất: %s' % ESCALATE,
            'Không cam kết thời gian giao, số tiền, hay chính sách nếu ngữ cảnh không nêu rõ.',
        ]
        if self.policy_text:
            parts.append('CHÍNH SÁCH CÔNG TY:\n' + self.policy_text)
        if kb_snippets:
            parts.append('KIẾN THỨC (Knowledge Base):\n' + '\n---\n'.join(kb_snippets))
        if self.include_partner_context:
            pc = self._partner_context(partner)
            if pc:
                parts.append('DỮ LIỆU KHÁCH HÀNG (chỉ của khách này):\n' + pc)
        return '\n\n'.join(parts)

    def _answer(self, partner, question):
        """Trả (answer, escalate). Không bao giờ raise ra ngoài (lỗi → chuyển người)."""
        self.ensure_one()
        kb = self._retrieve_kb(question)
        kb_snippets = ['# %s\n%s' % (title, snip) for title, snip in kb]
        system = self._build_system_prompt(partner, kb_snippets)
        try:
            answer = self.env['mail.bot']._run_agent(question, system_prompt=system, use_tools=False)
        except Exception:
            _logger.exception('AI CSKH: lỗi gọi LLM → chuyển nhân viên')
            return ('', True)
        escalate = (not answer) or (ESCALATE in answer)
        answer = (answer or '').replace(ESCALATE, '').strip()
        return (answer, escalate)

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Nhật ký AI'),
            'res_model': 'vct.cs.ai.log', 'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
        }
