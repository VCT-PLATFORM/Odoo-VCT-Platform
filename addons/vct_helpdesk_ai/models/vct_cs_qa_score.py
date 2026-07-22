# Written for VCT Platform. Not part of Odoo S.A.
import json
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class VctCsQaScore(models.Model):
    """AutoQA: AI chấm điểm hội thoại đã đóng (thái độ/chính xác/tuân thủ) và gắn cờ
    ticket rủi ro cho người soát. Chấm sơ bộ; người vẫn quyết định cuối."""
    _name = 'vct.cs.qa.score'
    _description = 'Điểm QA hội thoại'
    _order = 'create_date desc'

    ticket_id = fields.Many2one('helpdesk.ticket', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='ticket_id.partner_id', store=True)
    team_id = fields.Many2one(related='ticket_id.team_id', store=True)
    score = fields.Integer('Điểm (0–100)')
    at_risk = fields.Boolean('Có nguy cơ', help='Khách giận, sai chính sách... cần soát lại.')
    notes = fields.Text('Nhận xét AI')
    reviewer_id = fields.Many2one('res.users', 'Người soát')
    reviewed = fields.Boolean('Đã soát')

    def _parse_json(self, raw):
        match = re.search(r'\{.*\}', raw or '', re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}

    @api.model
    def _generate_for(self, ticket):
        """Chấm 1 ticket. Trả về record điểm, hoặc False nếu không có hội thoại/AI lỗi."""
        text = ticket._conversation_text(limit=30)
        if not text.strip():
            return False
        system = ('Bạn là QA chăm sóc khách hàng. Chấm hội thoại theo thái độ, độ chính xác, '
                  'tuân thủ quy trình. CHỈ trả về JSON: '
                  '{"diem": <0-100>, "nguy_co": <true|false>, "nhan_xet": "<ngắn gọn tiếng Việt>"}')
        try:
            raw = self.env['mail.bot']._run_agent(text, system_prompt=system, use_tools=False)
        except Exception:
            _logger.exception('AutoQA: lỗi gọi LLM cho ticket %s', ticket.id)
            return False
        data = self._parse_json(raw)
        return self.create({
            'ticket_id': ticket.id,
            'score': int(data.get('diem') or 0),
            'at_risk': bool(data.get('nguy_co')),
            'notes': data.get('nhan_xet') or (raw or '')[:2000],
        })

    @api.model
    def _cron_autoqa(self, limit=50):
        """Chấm các ticket đã đóng (stage folded) chưa có điểm. Mặc định cron TẮT."""
        scored = self.search([]).ticket_id
        tickets = self.env['helpdesk.ticket'].search(
            [('stage_id.fold', '=', True), ('id', 'not in', scored.ids)], limit=limit)
        for ticket in tickets:
            try:
                with self.env.cr.savepoint():
                    self._generate_for(ticket)
            except Exception:
                _logger.exception('AutoQA: lỗi ticket %s', ticket.id)

    def action_mark_reviewed(self):
        self.write({'reviewed': True, 'reviewer_id': self.env.uid})
