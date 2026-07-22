# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestFinancialReport(AccountTestInvoicingCommon):
    """Books kept deliberately tiny so every figure below is checkable by hand:
    capital 1000, a sale of 500, a bill of 200.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data['default_journal_misc']
        cls.today = fields.Date.today()
        cls.entries = cls.env['account.move']
        cls.bank = cls.company_data['default_account_assets']
        cls.equity = cls._get_account('equity')
        cls.recv = cls.company_data['default_account_receivable']
        cls.payable = cls.company_data['default_account_payable']
        cls.income = cls.company_data['default_account_revenue']
        cls.expense = cls.company_data['default_account_expense']

        cls._post([(cls.bank, 1000, 0), (cls.equity, 0, 1000)])
        cls._post([(cls.recv, 500, 0), (cls.income, 0, 500)])
        cls._post([(cls.expense, 200, 0), (cls.payable, 0, 200)])

    @classmethod
    def _get_account(cls, account_type):
        return cls.env['account.account'].search([
            ('account_type', '=', account_type),
            ('company_ids', 'in', cls.env.company.id),
        ], limit=1)

    @classmethod
    def _post(cls, lines, date=None):
        move = cls.env['account.move'].create({
            'journal_id': cls.journal.id,
            'date': date or cls.today,
            'line_ids': [
                (0, 0, {'account_id': a.id, 'debit': d, 'credit': c, 'name': 'test'})
                for a, d, c in lines
            ],
        })
        move.action_post()
        cls.entries |= move
        return move

    def _report(self, report_type, **values):
        return self.env['account.financial.report'].create({
            'report_type': report_type,
            'company_id': self.env.company.id,
            **values,
        })

    def _totals(self, report):
        return {line.name.strip(): line.balance for line in report.line_ids if line.is_total}

    def test_balance_sheet_balances(self):
        totals = self._totals(self._report('balance_sheet'))
        self.assertAlmostEqual(totals['TỔNG TÀI SẢN'], 1500, 2, "bank 1000 + receivable 500")
        self.assertAlmostEqual(
            totals['TỔNG NGUỒN VỐN'], 1500, 2,
            "payable 200 + equity 1000 + undistributed result 300")
        self.assertAlmostEqual(
            totals['TỔNG TÀI SẢN'], totals['TỔNG NGUỒN VỐN'], 2,
            "the accounting identity must hold")

    def test_profit_loss(self):
        totals = self._totals(self._report('profit_loss'))
        self.assertAlmostEqual(totals['Cộng doanh thu'], 500, 2)
        self.assertAlmostEqual(totals['Cộng chi phí'], 200, 2)
        self.assertAlmostEqual(totals['Lợi nhuận thuần'], 300, 2)

    def test_current_year_earnings_reaches_the_balance_sheet(self):
        """The result is never on an account before closing, so the balance
        sheet has to derive it from the income/expense accounts."""
        report = self._report('balance_sheet')
        earnings = [
            line for line in report.line_ids
            if 'Lợi nhuận chưa phân phối năm nay' in line.name
        ]
        self.assertEqual(len(earnings), 1)
        self.assertAlmostEqual(earnings[0].balance, 300, 2)

    def test_draft_entries_excluded_unless_asked(self):
        draft = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': self.today,
            'line_ids': [
                (0, 0, {'account_id': self.bank.id, 'debit': 70, 'credit': 0, 'name': 'x'}),
                (0, 0, {'account_id': self.equity.id, 'debit': 0, 'credit': 70, 'name': 'x'}),
            ],
        })
        self.assertEqual(draft.state, 'draft')
        self.assertAlmostEqual(self._totals(self._report('balance_sheet'))['TỔNG TÀI SẢN'], 1500, 2)
        with_draft = self._report('balance_sheet', target_move='all')
        self.assertAlmostEqual(self._totals(with_draft)['TỔNG TÀI SẢN'], 1570, 2)
        self.assertAlmostEqual(
            self._totals(with_draft)['TỔNG NGUỒN VỐN'], 1570, 2,
            "including drafts must still balance")

    def test_profit_loss_respects_the_period(self):
        """P&L covers a window; the balance sheet stays cumulative."""
        self._post([(self.recv, 900, 0), (self.income, 0, 900)],
                   date=self.today - relativedelta(years=1))
        this_year = self._report(
            'profit_loss', date_from=self.today.replace(month=1, day=1), date_to=self.today)
        self.assertAlmostEqual(
            self._totals(this_year)['Cộng doanh thu'], 500, 2,
            "last year's 900 must not leak into this year's revenue")
        self.assertAlmostEqual(
            self._totals(self._report('balance_sheet'))['TỔNG TÀI SẢN'], 2400, 2,
            "the balance sheet is cumulative, so it does include it")

    def test_off_balance_accounts_ignored(self):
        off = self._get_account('off_balance')
        if not off:
            self.skipTest("no off-balance account in this chart")
        self._post([(off, 40, 0), (off, 0, 40)])
        self.assertAlmostEqual(self._totals(self._report('balance_sheet'))['TỔNG TÀI SẢN'], 1500, 2)

    def test_drill_down_from_a_balance_sheet_line_works(self):
        """The drill-down button was never exercised: line_ids is a non-stored
        compute, so the inverse report_id was never written and the button lost
        its report."""
        report = self._report('balance_sheet')
        line = next(l for l in report.line_ids if l.account_id)
        self.assertTrue(line.report_id, "the line must know its report")
        action = line.action_open_ledger()
        self.assertEqual(action['res_model'], 'account.move.line')
        self.assertIn(('account_id', '=', line.account_id.id), action['domain'])

    def test_lines_can_carry_a_statutory_code(self):
        """Every Ministry of Finance statement form is keyed by Mã số. The column
        must exist before the TT99 mapping can be filled in; it is deliberately
        empty until each line is mapped to a real form code."""
        report = self._report('balance_sheet')
        self.assertIn('code', report.line_ids._fields)
        self.assertTrue(all(not l.code for l in report.line_ids),
                        "no line may claim a form code until it is mapped to TT99")

    def test_statement_is_named_per_tt99(self):
        """TT99/2025 Điều 17.1 lists the four statements and B01-DN is
        'Báo cáo tình hình tài chính'. 'Bảng cân đối kế toán' appears once in the
        whole circular — at Điều 30.3, referring back to the pre-2026 TT200
        presentation. Using the retired name on a 2026 report is wrong.
        """
        labels = dict(self.env['account.financial.report']._fields['report_type'].selection)
        self.assertEqual(labels['balance_sheet'], 'Báo cáo tình hình tài chính')
        self.assertNotIn('Bảng cân đối kế toán', labels.values())
        self.assertEqual(
            self.env.ref('account_financial_report.action_balance_sheet').name,
            'Báo cáo tình hình tài chính')
