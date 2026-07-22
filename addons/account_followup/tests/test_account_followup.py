# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountFollowup(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.customer = cls.env['res.partner'].create({'name': 'Khách nợ', 'email': 'a@example.com'})
        cls.levels = cls.env['account.followup.level'].search([])

    def _invoice(self, amount, days_overdue, post=True):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': self.today - relativedelta(days=days_overdue),
            'invoice_date_due': self.today - relativedelta(days=days_overdue),
            'invoice_line_ids': [(0, 0, {
                'name': 'x', 'quantity': 1, 'price_unit': amount, 'tax_ids': [],
            })],
        })
        if post:
            invoice.action_post()
        return invoice

    def test_no_overdue_means_no_level(self):
        self._invoice(100, days_overdue=-5)  # due in the future
        self.assertFalse(self.customer.followup_level_id)
        self.assertAlmostEqual(self.customer.followup_overdue_amount, 0, 2)

    def test_level_follows_the_oldest_overdue_invoice(self):
        self._invoice(100, days_overdue=10)
        self.customer.invalidate_recordset()
        self.assertEqual(self.customer.followup_level_id.delay, 7, "10 ngày quá hạn -> mức 7 ngày")

        self._invoice(50, days_overdue=45)
        self.customer.invalidate_recordset()
        self.assertEqual(self.customer.followup_level_id.delay, 30, "hoá đơn cũ nhất quyết định mức")
        self.assertAlmostEqual(self.customer.followup_overdue_amount, 150, 2, "cộng dồn cả hai")

    def test_draft_invoices_are_not_overdue(self):
        self._invoice(100, days_overdue=40, post=False)
        self.customer.invalidate_recordset()
        self.assertAlmostEqual(self.customer.followup_overdue_amount, 0, 2)
        self.assertFalse(self.customer.followup_level_id)

    def test_paid_invoice_drops_out(self):
        invoice = self._invoice(100, days_overdue=40)
        self.customer.invalidate_recordset()
        self.assertAlmostEqual(self.customer.followup_overdue_amount, 100, 2)

        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': self.today})._create_payments()
        self.customer.invalidate_recordset()
        self.assertAlmostEqual(
            self.customer.followup_overdue_amount, 0, 2, "đã thanh toán thì hết nợ quá hạn")

    def test_sending_posts_a_log_and_snoozes(self):
        self._invoice(100, days_overdue=10)
        self.customer.invalidate_recordset()
        before = len(self.customer.message_ids)
        self.customer.action_followup_send()
        self.assertGreater(len(self.customer.message_ids), before, "ghi lại đã nhắc")
        self.assertTrue(self.customer.followup_next_date, "đã hoãn tới lần nhắc sau")
        self.assertGreater(self.customer.followup_next_date, self.today)

    def test_sending_without_a_level_is_refused(self):
        with self.assertRaises(UserError):
            self.customer.action_followup_send()

    def test_cron_skips_snoozed_customers(self):
        self._invoice(100, days_overdue=10)
        self.customer.invalidate_recordset()
        self.assertIn(self.customer, self.env['res.partner']._followup_partners_to_remind())

        self.customer.followup_next_date = self.today + relativedelta(days=5)
        self.assertNotIn(self.customer, self.env['res.partner']._followup_partners_to_remind())

    def test_cron_reminds_due_customers_only(self):
        self._invoice(100, days_overdue=10)
        quiet = self.env['res.partner'].create({'name': 'Khách ngoan'})
        self.customer.invalidate_recordset()
        reminded = self.env['res.partner']._cron_send_followup()
        self.assertIn(self.customer, reminded)
        self.assertNotIn(quiet, reminded)
