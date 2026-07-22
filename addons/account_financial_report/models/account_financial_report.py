# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import float_is_zero

# (account_type, label) grouped into the sections of each statement, in display
# order. Odoo derives internal_group from account_type, but the statements need
# a finer split than the 6 internal groups give.
BALANCE_SHEET = [
    ('assets', 'TÀI SẢN', [
        ('current', 'A. Tài sản ngắn hạn', [
            ('asset_cash', 'Tiền và tương đương tiền'),
            ('asset_receivable', 'Phải thu khách hàng'),
            ('asset_current', 'Tài sản ngắn hạn khác'),
            ('asset_prepayments', 'Chi phí trả trước'),
        ]),
        ('non_current', 'B. Tài sản dài hạn', [
            ('asset_fixed', 'Tài sản cố định'),
            ('asset_non_current', 'Tài sản dài hạn khác'),
        ]),
    ]),
    ('liabilities', 'NGUỒN VỐN', [
        ('liability', 'A. Nợ phải trả', [
            ('liability_payable', 'Phải trả người bán'),
            ('liability_credit_card', 'Thẻ tín dụng'),
            ('liability_current', 'Nợ ngắn hạn khác'),
            ('liability_non_current', 'Nợ dài hạn'),
        ]),
        ('equity', 'B. Vốn chủ sở hữu', [
            ('equity', 'Vốn chủ sở hữu'),
            ('equity_unaffected', 'Lợi nhuận chưa phân phối'),
        ]),
    ]),
]

PROFIT_LOSS = [
    ('income', 'DOANH THU', [
        ('income', 'Doanh thu bán hàng và cung cấp dịch vụ'),
        ('income_other', 'Doanh thu khác'),
    ]),
    ('expense', 'CHI PHÍ', [
        ('expense_direct_cost', 'Giá vốn hàng bán'),
        ('expense', 'Chi phí hoạt động'),
        ('expense_depreciation', 'Chi phí khấu hao'),
        ('expense_other', 'Chi phí khác'),
    ]),
]

# Sections whose figures read naturally as credit-positive.
CREDIT_POSITIVE = {'liabilities', 'income'}


class AccountFinancialReport(models.TransientModel):
    _name = 'account.financial.report'
    _description = 'Báo cáo tài chính'

    @api.model
    def _default_date_from(self):
        return self.env.company.compute_fiscalyear_dates(fields.Date.context_today(self))['date_from']

    # TT99/2025 Điều 17.1 renamed this statement: as of 01/01/2026 there is no
    # "Bảng cân đối kế toán" — B01-DN is "Báo cáo tình hình tài chính". The
    # technical key stays 'balance_sheet' so stored data and actions keep working.
    report_type = fields.Selection([
        ('balance_sheet', 'Báo cáo tình hình tài chính'),
        ('profit_loss', 'Báo cáo kết quả hoạt động kinh doanh'),
    ], string='Loại báo cáo', required=True, default='balance_sheet')
    date_from = fields.Date(string='Từ ngày', required=True, default=_default_date_from)
    date_to = fields.Date(string='Đến ngày', required=True, default=fields.Date.context_today)
    target_move = fields.Selection([
        ('posted', 'Chỉ bút toán đã vào sổ'),
        ('all', 'Tất cả bút toán'),
    ], string='Bút toán', required=True, default='posted')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many(
        'account.financial.report.line', 'report_id', string='Dòng báo cáo',
        compute='_compute_line_ids')

    def _base_domain(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date', '<=', self.date_to),
            ('account_id.account_type', '!=', 'off_balance'),
        ]
        if self.target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('parent_state', 'in', ('draft', 'posted')))
        return domain

    def _balances_per_type(self, extra_domain=()):
        """Sum of balances per account_type, as a plain {type: balance} dict."""
        self.ensure_one()
        groups = self.env['account.move.line']._read_group(
            self._base_domain() + list(extra_domain),
            ['account_id'], ['balance:sum'],
        )
        totals = {}
        for account, balance in groups:
            totals[account.account_type] = totals.get(account.account_type, 0.0) + balance
        return totals

    def _balances_per_account(self, account_types, extra_domain=()):
        """[(account, balance)] for the given types, dropping empty accounts."""
        self.ensure_one()
        groups = self.env['account.move.line']._read_group(
            self._base_domain() + [('account_id.account_type', 'in', account_types)] + list(extra_domain),
            ['account_id'], ['balance:sum'], order='account_id',
        )
        rounding = self.company_id.currency_id.rounding
        return [(a, b) for a, b in groups if not float_is_zero(b, precision_rounding=rounding)]

    @api.depends('report_type', 'date_from', 'date_to', 'target_move', 'company_id')
    def _compute_line_ids(self):
        for report in self:
            builder = report._build_balance_sheet if report.report_type == 'balance_sheet' \
                else report._build_profit_loss
            report.line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in builder()]

    def _pl_period_domain(self):
        """P&L figures cover the requested period only, never earlier."""
        return [('date', '>=', self.date_from)]

    def _earnings(self, date_from=None, date_to=None):
        """Net result (credit-positive) over an optional date window."""
        self.ensure_one()
        extra = []
        if date_from:
            extra.append(('date', '>=', date_from))
        if date_to:
            extra.append(('date', '<=', date_to))
        totals = self._balances_per_type(extra)
        pnl = sum(
            balance for account_type, balance in totals.items()
            if account_type.startswith(('income', 'expense'))
        )
        return -pnl

    def _build_balance_sheet(self):
        self.ensure_one()
        vals, sequence = [], 0

        def add(name, level, balance=None, account=None, is_total=False, code=None):
            nonlocal sequence
            sequence += 1
            vals.append({
                'code': code,
                # report_id must be explicit: line_ids is a non-stored compute, so
                # assigning to it never writes the inverse, and action_open_ledger
                # then has no report to read its dates and domain from
                'report_id': self.id,
                # list cells collapse plain spaces, so indent with hard spaces
                'sequence': sequence, 'name': ' ' * (4 * level) + name, 'level': level,
                'balance': balance, 'account_id': account and account.id,
                'is_total': is_total,
            })

        fy_start = self.company_id.compute_fiscalyear_dates(self.date_to)['date_from']
        # Undistributed result never sits on an account until the books are
        # closed, so it is derived from the income/expense accounts instead.
        earnings_prior = self._earnings(date_to=fy_start - relativedelta(days=1))
        earnings_current = self._earnings(date_from=fy_start)

        for section_key, section_name, groups in BALANCE_SHEET:
            add(section_name, 0)
            section_total = 0.0
            for _group_key, group_name, types in groups:
                group_total = 0.0
                group_vals = []
                for account_type, type_name in types:
                    for account, balance in self._balances_per_account([account_type]):
                        shown = -balance if section_key in CREDIT_POSITIVE else balance
                        group_vals.append((f'{account.code} {account.name}', 3, shown, account))
                        group_total += shown
                if _group_key == 'equity':
                    if earnings_prior:
                        group_vals.append(('Lợi nhuận chưa phân phối các năm trước', 3, earnings_prior, None))
                        group_total += earnings_prior
                    if earnings_current:
                        group_vals.append(('Lợi nhuận chưa phân phối năm nay', 3, earnings_current, None))
                        group_total += earnings_current
                add(group_name, 1, group_total)
                for name, level, balance, account in group_vals:
                    add(name, level, balance, account)
                section_total += group_total
            add(f'TỔNG {section_name}', 0, section_total, is_total=True)
        return vals

    def _build_profit_loss(self):
        self.ensure_one()
        vals, sequence = [], 0

        def add(name, level, balance=None, account=None, is_total=False, code=None):
            nonlocal sequence
            sequence += 1
            vals.append({
                'code': code,
                # report_id must be explicit: line_ids is a non-stored compute, so
                # assigning to it never writes the inverse, and action_open_ledger
                # then has no report to read its dates and domain from
                'report_id': self.id,
                # list cells collapse plain spaces, so indent with hard spaces
                'sequence': sequence, 'name': ' ' * (4 * level) + name, 'level': level,
                'balance': balance, 'account_id': account and account.id,
                'is_total': is_total,
            })

        period = self._pl_period_domain()
        totals = {}
        for section_key, section_name, types in PROFIT_LOSS:
            section_total = 0.0
            rows = []
            for account_type, _type_name in types:
                for account, balance in self._balances_per_account([account_type], period):
                    shown = -balance if section_key in CREDIT_POSITIVE else balance
                    rows.append((f'{account.code} {account.name}', shown, account))
                    section_total += shown
            add(section_name, 0)
            for name, balance, account in rows:
                add(name, 2, balance, account)
            add(f'Cộng {section_name.lower()}', 1, section_total, is_total=True)
            totals[section_key] = section_total

        add('LỢI NHUẬN', 0)
        add('Lợi nhuận thuần', 1, totals['income'] - totals['expense'], is_total=True)
        return vals

    def action_show(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.financial.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'name': dict(self._fields['report_type'].selection)[self.report_type],
        }


class AccountFinancialReportLine(models.TransientModel):
    _name = 'account.financial.report.line'
    _description = 'Dòng báo cáo tài chính'
    _order = 'sequence'

    report_id = fields.Many2one('account.financial.report', required=True, ondelete='cascade')
    sequence = fields.Integer()
    code = fields.Char(
        string='Mã số',
        help="Mã số chỉ tiêu theo biểu mẫu báo cáo tài chính của Bộ Tài chính. "
             "Bỏ trống nghĩa là dòng này chưa được ánh xạ vào biểu mẫu pháp định.")
    name = fields.Char(string='Chỉ tiêu')
    level = fields.Integer(help="0 là tiêu đề phần, số càng lớn càng thụt vào.")
    balance = fields.Monetary(string='Số tiền', currency_field='currency_id')
    currency_id = fields.Many2one(related='report_id.currency_id')
    account_id = fields.Many2one('account.account', string='Tài khoản')
    is_total = fields.Boolean()

    def action_open_ledger(self):
        """Drill down from a report line to the journal items behind it."""
        self.ensure_one()
        report = self.report_id
        domain = report._base_domain() + [('account_id', '=', self.account_id.id)]
        if report.report_type == 'profit_loss':
            domain += report._pl_period_domain()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name.strip(' '),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'search_default_group_by_account': 1},
        }
