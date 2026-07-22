# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AccountBudgetPost(models.Model):
    _name = 'account.budget.post'
    _description = 'Budgetary Position'
    _order = 'name'

    name = fields.Char("Tên vị trí ngân sách", required=True)
    account_ids = fields.Many2many('account.account', string="Tài khoản kế toán", required=True,
        domain="[('active', '=', True)]")
    company_id = fields.Many2one('res.company', string="Công ty", required=True,
        default=lambda self: self.env.company)


class CrossoveredBudget(models.Model):
    _name = 'crossovered.budget'
    _description = 'Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char("Tên ngân sách", required=True, tracking=True)
    user_id = fields.Many2one('res.users', string="Người phụ trách", default=lambda self: self.env.user, tracking=True)
    date_from = fields.Date("Ngày bắt đầu", required=True, tracking=True)
    date_to = fields.Date("Ngày kết thúc", required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('validate', 'Đã duyệt'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy bỏ')
    ], string="Trạng thái", default='draft', required=True, tracking=True)
    crossovered_budget_line = fields.One2many('crossovered.budget.lines', 'crossovered_budget_id', string="Dòng ngân sách chi tiết", copy=True)
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.write({'state': 'validate'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class CrossoveredBudgetLines(models.Model):
    _name = 'crossovered.budget.lines'
    _description = 'Budget Line'
    _order = 'crossovered_budget_id, id'

    crossovered_budget_id = fields.Many2one('crossovered.budget', string="Ngân sách", required=True, ondelete='cascade')
    general_budget_id = fields.Many2one('account.budget.post', string="Vị trí ngân sách", required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Tài khoản phân tích")
    date_from = fields.Date("Ngày bắt đầu", required=True)
    date_to = fields.Date("Ngày kết thúc", required=True)
    planned_amount = fields.Float("Số tiền dự kiến", required=True, digits=0,
        help="Số tiền dự kiến thu hoặc chi. Thu nhập ghi số dương, chi phí ghi số âm.")
    practical_amount = fields.Float("Số tiền thực tế", compute='_compute_practical_amount', digits=0)
    theoritical_amount = fields.Float("Số tiền lý thuyết", compute='_compute_theoritical_amount', digits=0)
    percentage = fields.Float("Tỷ lệ đạt (%)", compute='_compute_percentage')
    company_id = fields.Many2one('res.company', string="Công ty", related='crossovered_budget_id.company_id', store=True, readonly=True)

    @api.depends('general_budget_id', 'analytic_account_id', 'date_from', 'date_to')
    def _compute_practical_amount(self):
        for line in self:
            acc_ids = line.general_budget_id.account_ids.ids
            if not acc_ids or not line.date_from or not line.date_to:
                line.practical_amount = 0.0
                continue

            domain = [
                ('account_id', 'in', acc_ids),
                ('date', '>=', line.date_from),
                ('date', '<=', line.date_to),
                ('parent_state', '=', 'posted')
            ]
            if line.analytic_account_id:
                domain.append(('distribution_analytic_account_ids', 'in', line.analytic_account_id.id))

            move_lines = self.env['account.move.line'].search(domain)
            line.practical_amount = sum(move_lines.mapped('balance'))

    @api.depends('planned_amount', 'date_from', 'date_to')
    def _compute_theoritical_amount(self):
        today = fields.Date.today()
        for line in self:
            if not line.date_from or not line.date_to:
                line.theoritical_amount = 0.0
                continue

            if today < line.date_from:
                line.theoritical_amount = 0.0
            elif today > line.date_to:
                line.theoritical_amount = line.planned_amount
            else:
                elapsed_days = (today - line.date_from).days + 1
                total_days = (line.date_to - line.date_from).days + 1
                line.theoritical_amount = line.planned_amount * (elapsed_days / total_days)

    @api.depends('planned_amount', 'practical_amount')
    def _compute_percentage(self):
        for line in self:
            if line.planned_amount:
                line.percentage = (line.practical_amount / line.planned_amount) * 100
            else:
                line.percentage = 0.0
