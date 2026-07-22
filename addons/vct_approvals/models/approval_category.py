# Written for VCT Platform. Not part of Odoo S.A.
from odoo import api, fields, models


class ApprovalCategory(models.Model):
    """Loại yêu cầu phê duyệt (nghỉ phép, mua sắm, chi phí...). Định nghĩa người duyệt
    mặc định và số phê duyệt tối thiểu để yêu cầu được thông qua."""
    _name = 'approval.category'
    _description = 'Loại phê duyệt'
    _order = 'sequence, name'

    name = fields.Char('Tên loại', required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description = fields.Text('Mô tả')
    approval_minimum = fields.Integer('Số duyệt tối thiểu', default=1, required=True)
    user_ids = fields.Many2many('res.users', string='Người duyệt mặc định')
    has_amount = fields.Boolean('Có số tiền')
    has_date = fields.Boolean('Có thời hạn')
    color = fields.Integer('Màu')
    request_count = fields.Integer(compute='_compute_request_count')

    _minimum_positive = models.Constraint(
        'CHECK(approval_minimum > 0)', 'Số duyệt tối thiểu phải lớn hơn 0.')

    def _compute_request_count(self):
        counts = dict(self.env['approval.request']._read_group(
            [('category_id', 'in', self.ids)], groupby=['category_id'], aggregates=['__count']))
        for cat in self:
            cat.request_count = counts.get(cat, 0)

    def action_new_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'approval.request',
            'view_mode': 'form', 'context': {'default_category_id': self.id},
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.name,
            'res_model': 'approval.request', 'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
