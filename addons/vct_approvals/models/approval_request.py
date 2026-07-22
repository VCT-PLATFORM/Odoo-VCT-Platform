# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ApprovalRequest(models.Model):
    """Một yêu cầu phê duyệt. Được thông qua khi số người duyệt 'approved' đạt ngưỡng
    tối thiểu của loại; bị từ chối ngay khi một người duyệt 'refused'."""
    _name = 'approval.request'
    _description = 'Yêu cầu phê duyệt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Tiêu đề', required=True, tracking=True)
    category_id = fields.Many2one(
        'approval.category', string='Loại', required=True, tracking=True, ondelete='restrict')
    request_owner_id = fields.Many2one(
        'res.users', string='Người yêu cầu', default=lambda self: self.env.user, tracking=True)
    date = fields.Datetime('Ngày cần', tracking=True)
    amount = fields.Monetary('Số tiền', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    reason = fields.Html('Lý do / Nội dung')
    state = fields.Selection([
        ('new', 'Nháp'), ('pending', 'Đang chờ duyệt'),
        ('approved', 'Đã duyệt'), ('refused', 'Từ chối'), ('cancel', 'Đã huỷ'),
    ], default='new', tracking=True, string='Trạng thái')
    approver_ids = fields.One2many('approval.approver', 'request_id', string='Người duyệt')
    approval_minimum = fields.Integer(related='category_id.approval_minimum')
    has_amount = fields.Boolean(related='category_id.has_amount')
    has_date = fields.Boolean(related='category_id.has_date')
    approved_count = fields.Integer(compute='_compute_approver_stats')
    can_approve = fields.Boolean(compute='_compute_can_approve')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('approver_ids.status')
    def _compute_approver_stats(self):
        for req in self:
            req.approved_count = len(req.approver_ids.filtered(lambda a: a.status == 'approved'))

    @api.depends('approver_ids.user_id', 'approver_ids.status', 'state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        # phụ thuộc người dùng hiện tại; depends_context('uid') để cache key theo user
        for req in self:
            mine = req.approver_ids.filtered(lambda a: a.user_id == req.env.user)
            req.can_approve = req.state == 'pending' and bool(
                mine.filtered(lambda a: a.status in ('pending', 'new')))

    @api.onchange('category_id')
    def _onchange_category_id(self):
        """Nạp người duyệt mặc định của loại khi chọn loại."""
        if self.category_id and not self.approver_ids:
            self.approver_ids = [(0, 0, {'user_id': u.id}) for u in self.category_id.user_ids]

    def _ensure_approvers(self):
        for req in self:
            if not req.approver_ids and req.category_id.user_ids:
                req.approver_ids = [(0, 0, {'user_id': u.id}) for u in req.category_id.user_ids]

    # ---- Vòng đời ----
    def action_confirm(self):
        for req in self:
            if req.state != 'new':
                continue
            req._ensure_approvers()
            if not req.approver_ids:
                raise UserError(_('Cần ít nhất một người duyệt trước khi gửi.'))
            if req.approval_minimum > len(req.approver_ids):
                raise UserError(_('Số người duyệt (%(n)s) ít hơn ngưỡng tối thiểu (%(m)s).',
                                  n=len(req.approver_ids), m=req.approval_minimum))
            req.approver_ids.write({'status': 'pending'})
            req.state = 'pending'
            req._activate_activities()

    def _activate_activities(self):
        """Nhắc mỗi người duyệt còn 'pending' bằng một hoạt động To-Do."""
        self.ensure_one()
        for approver in self.approver_ids.filtered(lambda a: a.status == 'pending'):
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=approver.user_id.id,
                summary=_('Cần bạn duyệt: %s', self.name))

    def _current_approver(self):
        self.ensure_one()
        return self.approver_ids.filtered(lambda a: a.user_id == self.env.user)

    def action_approve(self):
        for req in self:
            approver = req._current_approver()
            if not approver:
                raise UserError(_('Bạn không nằm trong danh sách người duyệt.'))
            approver.status = 'approved'
            req._clear_my_activity()
            if req.approved_count >= req.approval_minimum:
                req.state = 'approved'
                req.activity_unlink(['mail.mail_activity_data_todo'])

    def action_refuse(self):
        for req in self:
            approver = req._current_approver()
            if not approver:
                raise UserError(_('Bạn không nằm trong danh sách người duyệt.'))
            approver.status = 'refused'
            req.state = 'refused'
            req.activity_unlink(['mail.mail_activity_data_todo'])

    def _clear_my_activity(self):
        self.ensure_one()
        self.activity_ids.filtered(lambda a: a.user_id == self.env.user).unlink()

    def action_withdraw(self):
        """Rút lại phê duyệt của mình (đưa yêu cầu về chờ)."""
        for req in self:
            approver = req._current_approver()
            if approver:
                approver.status = 'pending'
            if req.state in ('approved', 'refused'):
                req.state = 'pending'

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.activity_unlink(['mail.mail_activity_data_todo'])

    def action_draft(self):
        self.filtered(lambda r: r.state in ('cancel', 'refused')).write({'state': 'new'})
        for req in self:
            req.approver_ids.write({'status': 'new'})

    @api.constrains('approval_minimum', 'approver_ids')
    def _check_minimum(self):
        for req in self.filtered(lambda r: r.state == 'pending'):
            if req.approval_minimum > len(req.approver_ids):
                raise ValidationError(_('Ngưỡng duyệt tối thiểu lớn hơn số người duyệt.'))
