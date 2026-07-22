# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class ApprovalApprover(models.Model):
    _name = 'approval.approver'
    _description = 'Người duyệt yêu cầu'

    request_id = fields.Many2one('approval.request', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Người duyệt', required=True)
    status = fields.Selection([
        ('new', 'Mới'), ('pending', 'Chờ duyệt'), ('approved', 'Đã duyệt'), ('refused', 'Từ chối'),
    ], default='new', string='Trạng thái')
    company_id = fields.Many2one(related='request_id.company_id', store=True)

    _user_uniq = models.Constraint(
        'UNIQUE(request_id, user_id)', 'Mỗi người chỉ là người duyệt một lần trong một yêu cầu.')
