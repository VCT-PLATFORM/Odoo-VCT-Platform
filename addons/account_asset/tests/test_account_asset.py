# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountAsset(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data['default_journal_misc']
        cls.account_asset = cls.company_data['default_account_assets']
        cls.account_depreciation = cls.company_data['default_account_assets']
        cls.account_expense = cls.company_data['default_account_expense']

    def _asset(self, **values):
        return self.env['account.asset'].create({
            'name': 'Test asset',
            'original_value': 12000.0,
            'method_number': 12,
            'method_period': '1',
            'acquisition_date': fields.Date.from_string('2026-01-15'),
            'journal_id': self.journal.id,
            'account_asset_id': self.account_asset.id,
            'account_depreciation_id': self.account_depreciation.id,
            'account_expense_id': self.account_expense.id,
            **values,
        })

    def test_board_totals_match_the_depreciable_value(self):
        asset = self._asset()
        asset.action_validate()
        self.assertEqual(asset.state, 'open')
        self.assertEqual(len(asset.depreciation_move_ids), 12)
        total = sum(
            line.debit
            for move in asset.depreciation_move_ids
            for line in move.line_ids
            if line.account_id == self.account_expense
        )
        self.assertAlmostEqual(total, 12000.0, 2, "12 x 1000")

    def test_salvage_value_is_not_depreciated(self):
        asset = self._asset(original_value=12000.0, salvage_value=2000.0)
        self.assertAlmostEqual(asset.total_depreciable, 10000.0, 2)
        asset.action_validate()
        total = sum(
            line.debit
            for move in asset.depreciation_move_ids
            for line in move.line_ids
            if line.account_id == self.account_expense
        )
        self.assertAlmostEqual(total, 10000.0, 2, "the salvage value stays on the books")

    def test_rounding_lands_on_the_last_period(self):
        """10000/3 does not divide: the board must still total exactly 10000."""
        asset = self._asset(original_value=10000.0, method_number=3)
        asset.action_validate()
        amounts = sorted(
            line.debit
            for move in asset.depreciation_move_ids
            for line in move.line_ids
            if line.account_id == self.account_expense
        )
        self.assertAlmostEqual(sum(amounts), 10000.0, 2)
        self.assertEqual(len(amounts), 3)
        self.assertAlmostEqual(amounts[0], 3333.33, 2)
        self.assertAlmostEqual(amounts[-1], 3333.34, 2, "the remainder goes to the last period")

    def test_entries_are_balanced_and_use_the_right_accounts(self):
        asset = self._asset()
        asset.action_validate()
        move = asset.depreciation_move_ids[0]
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')), 1000.0, 2)
        self.assertAlmostEqual(sum(move.line_ids.mapped('credit')), 1000.0, 2)
        debit = move.line_ids.filtered(lambda l: l.debit)
        credit = move.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(debit.account_id, self.account_expense, "chi phí khấu hao ghi Nợ")
        self.assertEqual(credit.account_id, self.account_depreciation, "hao mòn luỹ kế ghi Có")

    def test_periods_are_monthly_and_land_on_month_end(self):
        asset = self._asset(acquisition_date=fields.Date.from_string('2026-01-15'))
        asset.action_validate()
        dates = sorted(asset.depreciation_move_ids.mapped('date'))
        self.assertEqual(str(dates[0]), '2026-01-31', "first period closes the acquisition month")
        self.assertEqual(str(dates[1]), '2026-02-28')
        self.assertEqual(str(dates[-1]), '2026-12-31')

    def test_yearly_period(self):
        asset = self._asset(method_number=3, method_period='12')
        asset.action_validate()
        dates = sorted(asset.depreciation_move_ids.mapped('date'))
        self.assertEqual([str(d) for d in dates], ['2026-01-31', '2027-01-31', '2028-01-31'])

    def test_cron_posts_only_due_entries_and_updates_book_value(self):
        asset = self._asset()
        asset.action_validate()
        self.assertAlmostEqual(asset.book_value, 12000.0, 2, "nothing posted yet")

        self.env['account.asset']._cron_post_depreciation(
            date=fields.Date.from_string('2026-03-31'))
        posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
        self.assertEqual(len(posted), 3, "January, February and March are due")
        self.assertAlmostEqual(asset.depreciated_value, 3000.0, 2)
        self.assertAlmostEqual(asset.book_value, 9000.0, 2)
        self.assertEqual(asset.state, 'open')

    def test_asset_closes_once_fully_depreciated(self):
        asset = self._asset()
        asset.action_validate()
        self.env['account.asset']._cron_post_depreciation(
            date=fields.Date.from_string('2027-01-01'))
        self.assertAlmostEqual(asset.book_value, 0.0, 2)
        self.assertEqual(asset.state, 'close', "nothing left to depreciate")

    def test_cannot_reset_to_draft_once_posted(self):
        asset = self._asset()
        asset.action_validate()
        self.env['account.asset']._cron_post_depreciation(
            date=fields.Date.from_string('2026-01-31'))
        with self.assertRaises(UserError):
            asset.action_set_to_draft()

    def test_revalidating_keeps_posted_periods(self):
        asset = self._asset()
        asset.action_validate()
        self.env['account.asset']._cron_post_depreciation(
            date=fields.Date.from_string('2026-02-28'))
        asset._build_board()
        self.assertEqual(len(asset.depreciation_move_ids), 12, "no duplicated periods")
        self.assertEqual(len(asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')), 2)

    def test_salvage_value_above_original_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._asset(original_value=1000.0, salvage_value=1500.0)
