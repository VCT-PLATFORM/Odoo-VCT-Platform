# Written for VCT Platform. Not part of Odoo S.A.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSocialSales(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env['helpdesk.team'].create({'name': 'SS team'})
        cls.zalo = cls.env['vct.zalo.account'].create({
            'name': 'OA', 'oa_id': 'OASS', 'default_team_id': cls.team.id})
        cls.msg = cls.env['vct.messenger.account'].create({
            'name': 'Page', 'page_id': 'PSS', 'default_team_id': cls.team.id})
        cls.product = cls.env['product.product'].create({'name': 'Áo thun', 'list_price': 150000})

    def _zalo_conv(self, uid='u1'):
        return self.env['vct.zalo.conversation']._get_or_create(self.zalo, uid, 'Khách A')

    def test_zalo_conv_opens_order_wizard(self):
        conv = self._zalo_conv()
        action = conv.action_create_order()
        self.assertEqual(action['res_model'], 'vct.social.order.wizard')
        wiz = self.env['vct.social.order.wizard'].browse(action['res_id'])
        self.assertEqual(wiz.partner_id, conv.partner_id)
        self.assertIn('Zalo', wiz.source)

    def test_wizard_creates_sale_order(self):
        conv = self._zalo_conv('u2')
        wiz = self.env['vct.social.order.wizard'].browse(conv.action_create_order()['res_id'])
        wiz.line_ids = [(0, 0, {'product_id': self.product.id, 'quantity': 2, 'price_unit': 150000})]
        res = wiz.action_create_order()
        order = self.env['sale.order'].browse(res['res_id'])
        self.assertEqual(order.partner_id, conv.partner_id)
        self.assertTrue(order.social_source, 'đơn phải đánh dấu nguồn hội thoại')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_id, self.product)
        self.assertGreater(order.amount_total, 0)

    def test_wizard_requires_lines(self):
        partner = self.env['res.partner'].create({'name': 'X'})
        wiz = self.env['vct.social.order.wizard'].create({'partner_id': partner.id})
        with self.assertRaises(UserError):
            wiz.action_create_order()

    def test_messenger_conv_opens_wizard(self):
        conv = self.env['vct.messenger.conversation']._get_or_create(self.msg, 'psid1', 'FB Khách')
        wiz = self.env['vct.social.order.wizard'].browse(conv.action_create_order()['res_id'])
        self.assertEqual(wiz.partner_id, conv.partner_id)
        self.assertIn('Messenger', wiz.source)
