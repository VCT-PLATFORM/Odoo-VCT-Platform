# Written for VCT Platform. Not part of Odoo S.A.
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRental(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'KH Thuê'})
        cls.income = cls.env['account.account'].create({
            'name': 'DT thuê', 'code': '701RENT', 'account_type': 'income'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Bán thuê', 'type': 'sale', 'code': 'RENTJ'})
        cls.product = cls.env['product.product'].create({
            'name': 'Máy chiếu', 'rental_ok': True, 'rental_price_day': 500000, 'rental_stock': 2})
        cls.product.property_account_income_id = cls.income

    def _order(self, days=3, qty=1, start=None):
        start = start or fields.Datetime.now()
        return self.env['vct.rental.order'].create({
            'partner_id': self.partner.id,
            'date_start': start, 'date_return': start + timedelta(days=days),
            'line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': qty, 'price_day': 500000})]})

    def test_name_sequence(self):
        self.assertTrue(self._order().name.startswith('RENT'))

    def test_duration_and_pricing(self):
        order = self._order(days=3, qty=2)
        self.assertEqual(order.duration_days, 3)
        self.assertEqual(order.line_ids.price_subtotal, 500000 * 3 * 2)
        self.assertEqual(order.amount_total, 500000 * 3 * 2)

    def test_lifecycle(self):
        order = self._order()
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')
        order.action_pickup()
        self.assertEqual(order.state, 'picked_up')
        order.action_return()
        self.assertEqual(order.state, 'returned')
        self.assertTrue(order.date_returned)

    def test_availability_blocks_overbooking(self):
        start = fields.Datetime.now()
        o1 = self._order(days=3, qty=2, start=start)
        o1.action_confirm()
        o2 = self._order(days=3, qty=1, start=start)   # trùng kỳ, vượt tồn 2
        with self.assertRaises(UserError):
            o2.action_confirm()

    def test_availability_ok_when_not_overlapping(self):
        start = fields.Datetime.now()
        o1 = self._order(days=2, qty=2, start=start)
        o1.action_confirm()
        o2 = self._order(days=2, qty=2, start=start + timedelta(days=5))
        o2.action_confirm()   # không trùng kỳ → không lỗi
        self.assertEqual(o2.state, 'confirmed')

    def test_create_invoice(self):
        order = self._order(days=3, qty=1)
        move = order._create_invoice()
        self.assertEqual(move.vct_rental_order_id, order)
        self.assertEqual(move.amount_untaxed, 500000 * 3, 'qty×ngày × giá/ngày')
