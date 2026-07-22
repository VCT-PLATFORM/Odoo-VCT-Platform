# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubscription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'KH Thuê bao'})
        cls.plan_m = cls.env.ref('vct_subscription.plan_monthly')
        cls.plan_y = cls.env.ref('vct_subscription.plan_yearly')
        # kế toán tối thiểu để sinh hoá đơn
        cls.income = cls.env['account.account'].create({
            'name': 'Doanh thu TB', 'code': '701SUB', 'account_type': 'income'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Bán TB', 'type': 'sale', 'code': 'SUBJ'})
        cls.product = cls.env['product.product'].create({'name': 'Gói SP', 'list_price': 100000})
        cls.product.property_account_income_id = cls.income

    def _sub(self, plan=None):
        return self.env['vct.subscription'].create({
            'partner_id': self.partner.id, 'plan_id': (plan or self.plan_m).id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id, 'name': 'Gói', 'quantity': 1, 'price_unit': 100000})]})

    def test_name_sequence_assigned(self):
        sub = self._sub()
        self.assertTrue(sub.name.startswith('TB'), 'phải cấp số theo sequence')

    def test_totals_and_mrr(self):
        sub_m = self._sub(self.plan_m)
        self.assertEqual(sub_m.recurring_total, 100000)
        self.assertEqual(sub_m.mrr, 100000, 'gói tháng: MRR = tổng kỳ')
        sub_y = self._sub(self.plan_y)
        self.assertAlmostEqual(sub_y.mrr, 100000 / 12.0, places=2, msg='gói năm: MRR = tổng/12')

    def test_start_sets_next_invoice(self):
        sub = self._sub()
        sub.action_start()
        self.assertEqual(sub.state, 'progress')
        self.assertTrue(sub.next_invoice_date)

    def test_start_requires_lines(self):
        sub = self.env['vct.subscription'].create({
            'partner_id': self.partner.id, 'plan_id': self.plan_m.id})
        with self.assertRaises(UserError):
            sub.action_start()

    def test_create_invoice_links_back(self):
        sub = self._sub()
        move = sub._create_invoice()
        self.assertEqual(move.vct_subscription_id, sub)
        self.assertEqual(move.move_type, 'out_invoice')
        self.assertEqual(move.amount_untaxed, 100000)

    def test_cron_generates_and_bumps_date(self):
        sub = self._sub()
        sub.action_start()
        old = fields.Date.subtract(fields.Date.context_today(sub), days=1)
        sub.next_invoice_date = old
        self.env['vct.subscription']._cron_generate_invoices()
        self.assertEqual(sub.invoice_count, 1, 'cron phải sinh 1 hoá đơn')
        self.assertGreater(sub.next_invoice_date, old, 'phải đẩy ngày hoá đơn kế tiếp')
