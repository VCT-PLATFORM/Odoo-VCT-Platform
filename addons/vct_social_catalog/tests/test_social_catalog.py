# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSocialCatalog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.zalo_acc_cls = type(cls.env['vct.zalo.account'])
        cls.team = cls.env['helpdesk.team'].create({'name': 'Cat team'})
        cls.zalo = cls.env['vct.zalo.account'].create({
            'name': 'OA', 'oa_id': 'OACAT', 'default_team_id': cls.team.id, 'access_token': 'T'})
        cls.conv = cls.env['vct.zalo.conversation']._get_or_create(cls.zalo, 'z1', 'Khách')
        cls.p1 = cls.env['product.product'].create({'name': 'Áo thun', 'list_price': 150000})
        cls.p2 = cls.env['product.product'].create({'name': 'Quần jean', 'list_price': 350000})

    def _wizard(self):
        return self.env['vct.social.share.wizard'].browse(
            self.conv.action_share_products()['res_id'])

    def test_share_opens_wizard(self):
        action = self.conv.action_share_products()
        self.assertEqual(action['res_model'], 'vct.social.share.wizard')
        wiz = self.env['vct.social.share.wizard'].browse(action['res_id'])
        self.assertEqual(wiz.res_model, 'vct.zalo.conversation')
        self.assertEqual(wiz.res_id, self.conv.id)

    def test_share_sends_each_product(self):
        wiz = self._wizard()
        wiz.product_ids = [(6, 0, [self.p1.id, self.p2.id])]
        with patch.object(self.zalo_acc_cls, '_send_message', autospec=True, return_value=True) as m:
            wiz.action_share()
        self.assertEqual(m.call_count, 2, 'mỗi sản phẩm gửi một thẻ')
        sent = [call.args[2] for call in m.call_args_list]   # (self, recipient, text)
        self.assertTrue(any('Áo thun' in t and '150,000' in t for t in sent))

    def test_share_requires_products(self):
        wiz = self._wizard()
        with self.assertRaises(UserError):
            wiz.action_share()

    def test_format_card_has_name_and_price(self):
        wiz = self.env['vct.social.share.wizard'].create({
            'res_model': 'vct.zalo.conversation', 'res_id': self.conv.id, 'include_price': True})
        card = wiz._format_card(self.p1)
        self.assertIn('Áo thun', card)
        self.assertIn('150,000', card)
