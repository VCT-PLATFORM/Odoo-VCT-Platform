# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PlanningRole(models.Model):
    _name = 'planning.role'
    _description = 'Vai trò ca làm việc'
    _order = 'name'

    name = fields.Char(string='Vai trò', required=True, translate=True)
    color = fields.Integer(string='Màu')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'Đã có vai trò trùng tên.',
    )


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _description = 'Ca làm việc'
    _inherit = ['mail.thread']
    _order = 'start_datetime, id'
    _check_company_auto = True

    name = fields.Char(string='Ghi chú', tracking=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Nhân viên', tracking=True, check_company=True,
        help="Bỏ trống để tạo ca chưa phân công, ai rảnh thì nhận.")
    user_id = fields.Many2one(related='employee_id.user_id', store=True, string='Người dùng')
    role_id = fields.Many2one('planning.role', string='Vai trò', tracking=True)
    repeat_weeks = fields.Integer(
        string='Lặp trong (tuần)', default=4,
        help="Số tuần kế tiếp sẽ được nhân bản khi bấm Lặp hàng tuần.")
    project_id = fields.Many2one('project.project', string='Dự án', check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True, default=lambda self: self.env.company)

    start_datetime = fields.Datetime(string='Bắt đầu', required=True, tracking=True)
    end_datetime = fields.Datetime(string='Kết thúc', required=True, tracking=True)
    allocated_hours = fields.Float(
        string='Số giờ', compute='_compute_allocated_hours', store=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('published', 'Đã công bố'),
    ], string='Trạng thái', default='draft', required=True, tracking=True, copy=False)
    is_unassigned = fields.Boolean(
        string='Chưa phân công', compute='_compute_is_unassigned', store=True)
    conflict_count = fields.Integer(
        string='Số ca trùng giờ', compute='_compute_conflict_count',
        help="Số ca khác của cùng nhân viên bị chồng giờ với ca này.")
    leave_conflict = fields.Boolean(
        string='Trùng ngày nghỉ phép', compute='_compute_leave_conflict',
        help="Nhân viên đã được duyệt nghỉ phép trong khoảng thời gian của ca này.")
    color = fields.Integer(related='role_id.color')

    _start_before_end = models.Constraint(
        'CHECK(start_datetime < end_datetime)',
        'Giờ kết thúc phải sau giờ bắt đầu.',
    )

    @api.depends('start_datetime', 'end_datetime')
    def _compute_allocated_hours(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime:
                delta = slot.end_datetime - slot.start_datetime
                slot.allocated_hours = delta.total_seconds() / 3600
            else:
                slot.allocated_hours = 0.0

    @api.depends('employee_id')
    def _compute_is_unassigned(self):
        for slot in self:
            slot.is_unassigned = not slot.employee_id

    @api.depends('employee_id', 'start_datetime', 'end_datetime')
    def _compute_conflict_count(self):
        for slot in self:
            slot.conflict_count = len(slot._overlapping_slots())

    @api.depends('employee_id', 'start_datetime', 'end_datetime')
    def _compute_leave_conflict(self):
        for slot in self:
            slot.leave_conflict = bool(slot._overlapping_leaves())

    def _overlapping_leaves(self):
        """Approved time off running during this shift. Rostering somebody who
        is on leave is the failure this module used to ship with: a shift and a
        holiday are not the same object, so the shift-vs-shift check misses it."""
        self.ensure_one()
        if not self.employee_id or not self.start_datetime or not self.end_datetime:
            return self.env['hr.leave']
        return self.env['hr.leave'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<', self.end_datetime),
            ('date_to', '>', self.start_datetime),
        ])

    def _overlapping_slots(self):
        """Other shifts of the same employee running at the same time.

        Unassigned shifts never clash: nobody is booked yet.
        """
        self.ensure_one()
        if not self.employee_id or not self.start_datetime or not self.end_datetime:
            return self.browse()
        return self.search([
            ('id', '!=', self.id or 0),
            ('employee_id', '=', self.employee_id.id),
            # touching end-to-start is not an overlap: 08-12 and 12-16 are fine
            ('start_datetime', '<', self.end_datetime),
            ('end_datetime', '>', self.start_datetime),
        ])

    def action_view_conflicts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ca trùng giờ'),
            'res_model': 'planning.slot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._overlapping_slots().ids)],
        }

    def action_publish(self):
        """Publish the shifts and tell the assigned employees."""
        for slot in self:
            if not slot.employee_id:
                raise UserError(_("Ca chưa phân công thì chưa công bố được: hãy chọn nhân viên."))
        self.write({'state': 'published'})
        template = self.env.ref('planning.mail_template_slot_published', raise_if_not_found=False)
        if template:
            for slot in self.filtered(lambda s: s.employee_id.work_email):
                template.send_mail(slot.id, force_send=False)
        return True

    def action_unpublish(self):
        self.write({'state': 'draft'})

    def action_assign_to_me(self):
        """Let an employee take an open shift."""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_(
                "Tài khoản %s chưa gắn với nhân viên nào.", self.env.user.display_name))
        for slot in self:
            if slot.employee_id:
                raise UserError(_("Ca này đã có người nhận rồi."))
        self.write({'employee_id': employee.id})

    @api.model
    def action_copy_previous_week(self, date_start=None):
        """Rebuild a week from the one before it, which is how most rosters are
        actually made. Shifts already present in the target week are left alone.
        """
        date_start = fields.Datetime.to_datetime(date_start) if date_start \
            else fields.Datetime.now()
        target_start = date_start - relativedelta(days=date_start.weekday(), hour=0,
                                                  minute=0, second=0, microsecond=0)
        target_end = target_start + relativedelta(days=7)
        source_start = target_start - relativedelta(days=7)

        previous = self.search([
            ('start_datetime', '>=', source_start),
            ('start_datetime', '<', target_start),
        ])
        existing = self.search_count([
            ('start_datetime', '>=', target_start),
            ('start_datetime', '<', target_end),
        ])
        if existing:
            raise UserError(_("Tuần này đã có ca rồi; hãy xoá bớt trước khi sao chép."))
        if not previous:
            raise UserError(_("Tuần trước không có ca nào để sao chép."))
        return self.create([{
            'name': slot.name,
            'employee_id': slot.employee_id.id,
            'role_id': slot.role_id.id,
            'project_id': slot.project_id.id,
            'company_id': slot.company_id.id,
            'start_datetime': slot.start_datetime + relativedelta(days=7),
            'end_datetime': slot.end_datetime + relativedelta(days=7),
            'state': 'draft',
        } for slot in previous])

    def action_repeat_weekly_button(self):
        """Form button: repeat this shift over the next N weeks."""
        self.ensure_one()
        return self.action_repeat_weekly(weeks=self.repeat_weeks)

    def action_repeat_weekly(self, weeks=4):
        """Duplicate each shift onto the following weeks."""
        if weeks < 1:
            raise UserError(_("Số tuần lặp phải lớn hơn 0."))
        values = []
        for slot in self:
            for week in range(1, weeks + 1):
                values.append({
                    'name': slot.name,
                    'employee_id': slot.employee_id.id,
                    'role_id': slot.role_id.id,
                    'project_id': slot.project_id.id,
                    'company_id': slot.company_id.id,
                    'start_datetime': slot.start_datetime + relativedelta(weeks=week),
                    'end_datetime': slot.end_datetime + relativedelta(weeks=week),
                    'state': 'draft',
                })
        return self.create(values)
