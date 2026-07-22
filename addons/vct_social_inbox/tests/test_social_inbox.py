# Written for VCT Platform. Not part of Odoo S.A.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSocialInbox(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Thread = cls.env['vct.social.thread']
        cls.team = cls.env['helpdesk.team'].create({'name': 'IB team'})
        cls.zalo = cls.env['vct.zalo.account'].create({
            'name': 'OA', 'oa_id': 'OAIB', 'default_team_id': cls.team.id})
        cls.msg = cls.env['vct.messenger.account'].create({
            'name': 'Page', 'page_id': 'PIB', 'default_team_id': cls.team.id})
        cls.zconv = cls.env['vct.zalo.conversation']._get_or_create(cls.zalo, 'z1', 'Zalo Khách')
        cls.mconv = cls.env['vct.messenger.conversation']._get_or_create(cls.msg, 'm1', 'FB Khách')

    def _zthread(self):
        return self.Thread.search(
            [('channel', '=', 'zalo'), ('partner_id', '=', self.zconv.partner_id.id)], limit=1)

    def _mthread(self):
        return self.Thread.search(
            [('channel', '=', 'messenger'), ('partner_id', '=', self.mconv.partner_id.id)], limit=1)

    def test_unifies_both_channels(self):
        z, m = self._zthread(), self._mthread()
        self.assertTrue(z and m, 'inbox phải gộp cả Zalo lẫn Messenger')
        self.assertEqual(z.res_model, 'vct.zalo.conversation')
        self.assertEqual(z.res_id_ref, self.zconv.id)
        self.assertEqual(m.res_model, 'vct.messenger.conversation')
        self.assertEqual(m.res_id_ref, self.mconv.id)

    def test_ids_no_clash(self):
        ids = self.Thread.search([]).ids
        self.assertEqual(len(ids), len(set(ids)), 'id trong view hợp nhất phải duy nhất')

    def test_chot_don_returns_wizard(self):
        action = self._zthread().action_chot_don()
        self.assertEqual(action['res_model'], 'vct.social.order.wizard')
        wiz = self.env['vct.social.order.wizard'].browse(action['res_id'])
        self.assertEqual(wiz.partner_id, self.zconv.partner_id)

    def test_open_source_dispatches(self):
        action = self._mthread().action_open_source()
        self.assertEqual(action['res_model'], 'vct.messenger.conversation')
        self.assertEqual(action['res_id'], self.mconv.id)
