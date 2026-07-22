# Written for VCT Platform. Not part of Odoo S.A.

from collections import defaultdict

from odoo import api, fields, models

# (field name, label, upper bound in days overdue; None = no bound)
BUCKETS = [
    ('amount_not_due', 'Chưa đến hạn', 0),
    ('amount_1_30', '1-30', 30),
    ('amount_31_60', '31-60', 60),
    ('amount_61_90', '61-90', 90),
    ('amount_91_120', '91-120', 120),
    ('amount_over_120', 'Trên 120', None),
]


class AccountAgedReport(models.TransientModel):
    _name = 'account.aged.report'
    _description = 'Công nợ theo tuổi nợ'

    report_type = fields.Selection([
        ('receivable', 'Công nợ phải thu theo tuổi nợ'),
        ('payable', 'Công nợ phải trả theo tuổi nợ'),
    ], string='Loại báo cáo', required=True, default='receivable')
    date_to = fields.Date(string='Tính đến ngày', required=True, default=fields.Date.context_today)
    target_move = fields.Selection([
        ('posted', 'Chỉ bút toán đã vào sổ'),
        ('all', 'Tất cả bút toán'),
    ], string='Bút toán', required=True, default='posted')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many(
        'account.aged.report.line', 'report_id', string='Dòng', compute='_compute_line_ids')

    def _line_domain(self):
        self.ensure_one()
        account_type = 'asset_receivable' if self.report_type == 'receivable' else 'liability_payable'
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', '=', account_type),
            ('reconciled', '=', False),
            ('date', '<=', self.date_to),
        ]
        domain.append(('parent_state', '=', 'posted') if self.target_move == 'posted'
                      else ('parent_state', 'in', ('draft', 'posted')))
        return domain

    def _bucket_index(self, days_overdue):
        """Which ageing column a line falls into. Not-yet-due is its own column,
        never bucket 1: a debt due tomorrow is not 1 day late."""
        if days_overdue <= 0:
            return 0
        for index, (_fname, _label, bound) in enumerate(BUCKETS):
            if bound is not None and index and days_overdue <= bound:
                return index
        return len(BUCKETS) - 1

    @api.depends('report_type', 'date_to', 'target_move', 'company_id')
    def _compute_line_ids(self):
        for report in self:
            lines = self.env['account.move.line'].search(report._line_domain())
            # a payable balance is a credit: show it positive, like the receivable side
            sign = 1 if report.report_type == 'receivable' else -1
            per_partner = defaultdict(lambda: [0.0] * len(BUCKETS))
            for line in lines:
                due = line.date_maturity or line.date
                index = report._bucket_index((report.date_to - due).days)
                per_partner[line.partner_id][index] += line.amount_residual * sign

            rounding = report.company_id.currency_id.rounding
            values = []
            for partner, amounts in per_partner.items():
                if report.company_id.currency_id.is_zero(sum(amounts)):
                    continue
                # report_id must be explicit: line_ids is a non-stored compute,
                # so assigning to it never writes the inverse and the drill-down
                # button would lose its report
                vals = {'report_id': report.id, 'partner_id': partner.id, 'total': sum(amounts)}
                vals.update({BUCKETS[i][0]: amounts[i] for i in range(len(BUCKETS))})
                values.append(vals)
            values.sort(key=lambda v: -v['total'])
            report.line_ids = [(5, 0, 0)] + [(0, 0, v) for v in values]

    def action_open_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Chi tiết công nợ'),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': self._line_domain(),
            'context': {'search_default_group_by_partner': 1},
        }


class AccountAgedReportLine(models.TransientModel):
    _name = 'account.aged.report.line'
    _description = 'Dòng công nợ theo tuổi nợ'
    _order = 'total desc'

    report_id = fields.Many2one('account.aged.report', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Đối tác')
    currency_id = fields.Many2one(related='report_id.currency_id')
    amount_not_due = fields.Monetary(string='Chưa đến hạn')
    amount_1_30 = fields.Monetary(string='1-30 ngày')
    amount_31_60 = fields.Monetary(string='31-60 ngày')
    amount_61_90 = fields.Monetary(string='61-90 ngày')
    amount_91_120 = fields.Monetary(string='91-120 ngày')
    amount_over_120 = fields.Monetary(string='Trên 120 ngày')
    total = fields.Monetary(string='Tổng')

    def action_open_items(self):
        self.ensure_one()
        action = self.report_id.action_open_items()
        action['domain'] = action['domain'] + [('partner_id', '=', self.partner_id.id)]
        action['name'] = self.partner_id.display_name
        return action
