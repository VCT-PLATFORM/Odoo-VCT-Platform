# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@tagged('post_install', '-at_install')
class TestShippingVN(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ship_cls = type(cls.env['vct.shipment'])
        cls.partner = cls.env['res.partner'].create({
            'name': 'KH Ship', 'phone': '0900000000', 'street': '123 Lê Lợi', 'city': 'HCM'})
        cls.ghn = cls.env.ref('vct_shipping_vn.carrier_ghn')
        cls.ghtk = cls.env.ref('vct_shipping_vn.carrier_ghtk')
        cls.vtp = cls.env.ref('vct_shipping_vn.carrier_viettelpost')
        (cls.ghn | cls.ghtk | cls.vtp).write({'token': 'TOK', 'shop_id': 'S1'})

    def _ship(self, carrier):
        return self.env['vct.shipment'].create({
            'carrier_id': carrier.id, 'partner_id': self.partner.id,
            'to_name': 'KH', 'to_phone': '0900000000', 'to_address': '123 Lê Lợi',
            'to_district_id': '1454', 'to_ward_code': '20308',
            'cod_amount': 200000, 'weight': 500})

    def test_ghn_create(self):
        ship = self._ship(self.ghn)
        resp = _Resp({'code': 200, 'data': {'order_code': 'GHN123', 'total_fee': 30000}})
        with patch.object(self.ship_cls, '_http_request', autospec=True, return_value=resp):
            ship.action_create_shipment()
        self.assertEqual(ship.tracking_code, 'GHN123')
        self.assertEqual(ship.fee, 30000)
        self.assertEqual(ship.state, 'created')

    def test_ghtk_create(self):
        ship = self._ship(self.ghtk)
        resp = _Resp({'success': True, 'order': {'label': 'GHTK9', 'fee': 25000}})
        with patch.object(self.ship_cls, '_http_request', autospec=True, return_value=resp):
            ship.action_create_shipment()
        self.assertEqual(ship.tracking_code, 'GHTK9')
        self.assertEqual(ship.fee, 25000)

    def test_viettelpost_create(self):
        ship = self._ship(self.vtp)
        resp = _Resp({'data': {'ORDER_NUMBER': 'VTP7', 'MONEY_TOTAL_FEE': 28000}})
        with patch.object(self.ship_cls, '_http_request', autospec=True, return_value=resp):
            ship.action_create_shipment()
        self.assertEqual(ship.tracking_code, 'VTP7')

    def test_create_requires_token(self):
        self.ghn.token = False
        ship = self._ship(self.ghn)
        with self.assertRaises(UserError):
            ship.action_create_shipment()

    def test_ghn_rejection_raises(self):
        ship = self._ship(self.ghn)
        resp = _Resp({'code': 400, 'message': 'sai địa chỉ', 'data': {}})
        with patch.object(self.ship_cls, '_http_request', autospec=True, return_value=resp):
            with self.assertRaises(UserError):
                ship.action_create_shipment()

    def test_sale_creates_shipment(self):
        product = self.env['product.product'].create({'name': 'SP', 'list_price': 100000})
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 2})]})
        action = order.action_create_shipment()
        ship = self.env['vct.shipment'].browse(action['res_id'])
        self.assertEqual(ship.sale_order_id, order)
        self.assertEqual(ship.partner_id, self.partner)
        self.assertEqual(ship.cod_amount, order.amount_total)
