# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class VctCsAiLog(models.Model):
    """Nhật ký mọi lượt AI trả lời khách — phục vụ QA (Phase 4) và truy vết."""
    _name = 'vct.cs.ai.log'
    _description = 'Nhật ký AI CSKH'
    _order = 'create_date desc'

    config_id = fields.Many2one('vct.cs.ai.config', ondelete='set null', index=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', ondelete='set null')
    question = fields.Text('Câu hỏi của khách')
    answer = fields.Text('AI trả lời')
    escalated = fields.Boolean('Đã chuyển nhân viên')
