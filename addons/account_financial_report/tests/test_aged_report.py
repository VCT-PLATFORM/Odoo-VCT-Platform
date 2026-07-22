# Written for VCT Platform. Not part of Odoo S.A.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAgedReport(AccountTestInvoicingCommon):
    """Every invoice below sits on a bucket edge on purpose: off-by-one is the
    classic way an ageing report lies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = date(2026, 6, 30)
        cls.customer = cls.env['res.partner'].create({'name': 'Khách A'})
        cls.other = cls.env['res.partner'].create({'name': 'Khách B'})

    def _invoice(self, partner, amount, days_overdue, move_type='out_invoice', post=True):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': self.today - relativedelta(days=max(days_overdue, 0) + 1),
            'invoice_date_due': self.today - relativedelta(days=days_overdue),
            'invoice_line_ids': [(0, 0, {
                'name': 'x', 'quantity': 1, 'price_unit': amount, 'tax_ids': [],
            })],
        })
        if post:
            move.action_post()
        return move

    def _report(self, report_type='receivable', **values):
        return self.env['account.aged.report'].create({
            'report_type': report_type, 'date_to': self.today,
            'company_id': self.env.company.id, **values,
        })

    def _row(self, report, partner):
        return report.line_ids.filtered(lambda l: l.partner_id == partner)

    def test_each_invoice_lands_in_its_own_bucket(self):
        for days, amount in [(-5, 100), (1, 200), (30, 300), (31, 400),
                             (90, 500), (121, 600)]:
            self._invoice(self.customer, amount, days_overdue=days)
        row = self._row(self._report(), self.customer)
        self.assertAlmostEqual(row.amount_not_due, 100, 2, "due in 5 days is not overdue")
        self.assertAlmostEqual(row.amount_1_30, 200 + 300, 2, "1 and 30 days both sit in 1-30")
        self.assertAlmostEqual(row.amount_31_60, 400, 2, "31 days rolls to the next bucket")
        self.assertAlmostEqual(row.amount_61_90, 500, 2)
        self.assertAlmostEqual(row.amount_over_120, 600, 2)
        self.assertAlmostEqual(row.total, 2100, 2)

    def test_due_today_is_not_yet_overdue(self):
        self._invoice(self.customer, 100, days_overdue=0)
        row = self._row(self._report(), self.customer)
        self.assertAlmostEqual(row.amount_not_due, 100, 2, "due today is not one day late")
        self.assertAlmostEqual(row.amount_1_30, 0, 2)

    def test_partners_are_kept_apart(self):
        self._invoice(self.customer, 100, days_overdue=10)
        self._invoice(self.other, 250, days_overdue=10)
        report = self._report()
        self.assertAlmostEqual(self._row(report, self.customer).total, 100, 2)
        self.assertAlmostEqual(self._row(report, self.other).total, 250, 2)

    def test_a_paid_invoice_drops_off(self):
        invoice = self._invoice(self.customer, 100, days_overdue=10)
        self.assertAlmostEqual(self._row(self._report(), self.customer).total, 100, 2)
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': self.today})._create_payments()
        self.assertFalse(self._row(self._report(), self.customer),
                         "settled debt must leave the report")

    def test_draft_invoices_are_excluded_unless_asked(self):
        self._invoice(self.customer, 100, days_overdue=10, post=False)
        self.assertFalse(self._row(self._report(), self.customer))
        self.assertAlmostEqual(
            self._row(self._report(target_move='all'), self.customer).total, 100, 2)

    def test_a_credit_note_nets_off(self):
        self._invoice(self.customer, 100, days_overdue=10)
        self._invoice(self.customer, 40, days_overdue=10, move_type='out_refund')
        self.assertAlmostEqual(self._row(self._report(), self.customer).total, 60, 2)

    def test_payables_are_shown_positive(self):
        """A payable is a credit balance; showing it negative would make every
        supplier total read as a minus."""
        self._invoice(self.customer, 100, days_overdue=10, move_type='in_invoice')
        row = self._row(self._report('payable'), self.customer)
        self.assertAlmostEqual(row.total, 100, 2)
        self.assertAlmostEqual(row.amount_1_30, 100, 2)

    def test_receivable_report_ignores_payables(self):
        self._invoice(self.customer, 100, days_overdue=10, move_type='in_invoice')
        self.assertFalse(self._row(self._report('receivable'), self.customer))

    def test_drill_down_targets_the_partner(self):
        self._invoice(self.customer, 100, days_overdue=10)
        # hold the report, like the form does: line_ids is a computed transient
        # o2m, so each recompute drops the previous lines and makes stale ids
        report = self._report()
        row = self._row(report, self.customer)
        action = row.action_open_items()
        self.assertIn(('partner_id', '=', self.customer.id), action['domain'])
        self.assertIn(('account_id.account_type', '=', 'asset_receivable'), action['domain'])
