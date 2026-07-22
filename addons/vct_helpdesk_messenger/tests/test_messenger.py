# Written for VCT Platform. Not part of Odoo S.A.
import hashlib
import hmac
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


class _Resp:
    content = b'{}'

    def json(self):
        return {}


@tagged('post_install', '-at_install')
class TestMessenger(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.acc_cls = type(cls.env['vct.messenger.account'])
        cls.team = cls.env['helpdesk.team'].create({'name': 'FB team'})
        cls.account = cls.env['vct.messenger.account'].create({
            'name': 'Page test', 'page_id': 'PAGE1', 'app_secret': 'SEC',
            'page_access_token': 'PTOK', 'verify_token': 'vok', 'default_team_id': cls.team.id})

    def test_inbound_creates_ticket(self):
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            ticket = self.account._handle_inbound('psid1', 'chào page')
        m.assert_not_called()
        conv = self.env['vct.messenger.conversation'].search(
            [('account_id', '=', self.account.id), ('psid', '=', 'psid1')])
        self.assertTrue(conv and conv.ticket_id == ticket)
        self.assertEqual(ticket.team_id, self.team)
        self.assertTrue(ticket.message_ids.filtered(lambda mm: 'chào page' in (mm.body or '')))

    def test_inbound_reuses_open_ticket(self):
        t1 = self.account._handle_inbound('psid2', 'lần 1')
        t2 = self.account._handle_inbound('psid2', 'lần 2')
        self.assertEqual(t1, t2)

    def test_agent_reply_sends(self):
        conv = self.env['vct.messenger.conversation']._get_or_create(self.account, 'psid9', 'Khách 9')
        conv._ensure_ticket()
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            conv.ticket_id.message_post(body='<p>Dạ vâng ạ</p>', message_type='comment',
                                        subtype_xmlid='mail.mt_comment')
        m.assert_called_once()
        self.assertEqual(m.call_args.kwargs['json_body']['recipient']['id'], 'psid9')

    def test_internal_note_not_sent(self):
        conv = self.env['vct.messenger.conversation']._get_or_create(self.account, 'psid10', 'K10')
        conv._ensure_ticket()
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            conv.ticket_id.message_post(body='note', message_type='comment',
                                        subtype_xmlid='mail.mt_note')
        m.assert_not_called()

    def test_signature_valid_and_invalid(self):
        raw = b'{"object":"page"}'
        good = 'sha256=' + hmac.new(b'SEC', raw, hashlib.sha256).hexdigest()
        self.assertTrue(self.account._verify_signature(raw, good))
        self.assertFalse(self.account._verify_signature(raw, 'sha256=bad'))

    def test_signature_skipped_without_secret(self):
        acc = self.env['vct.messenger.account'].create({'name': 'no sec', 'page_id': 'P9'})
        self.assertTrue(acc._verify_signature(b'{}', None))
