# Written for VCT Platform. Not part of Odoo S.A.
import hashlib
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


class _Resp:
    content = b'{"error":0}'

    def json(self):
        return {'error': 0}


@tagged('post_install', '-at_install')
class TestZalo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.acc_cls = type(cls.env['vct.zalo.account'])
        cls.team = cls.env['helpdesk.team'].create({'name': 'Đội Zalo'})
        cls.account = cls.env['vct.zalo.account'].create({
            'name': 'OA test', 'oa_id': 'OA123', 'app_id': 'APP1',
            'secret_key': 'SECRET', 'access_token': 'TOKEN', 'default_team_id': cls.team.id})

    # ---- nhận tin vào ----
    def test_inbound_creates_ticket_conversation_partner(self):
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            ticket = self.account._handle_inbound('u1', 'Xin chào shop')
        m.assert_not_called()  # tin vào không được dội ngược ra Zalo
        conv = self.env['vct.zalo.conversation'].search(
            [('account_id', '=', self.account.id), ('zalo_user_id', '=', 'u1')])
        self.assertTrue(conv, 'phải tạo hội thoại')
        self.assertEqual(conv.ticket_id, ticket)
        self.assertTrue(conv.partner_id, 'phải gắn partner')
        self.assertEqual(ticket.team_id, self.team, 'ticket vào đúng đội của OA')
        self.assertTrue(ticket.message_ids.filtered(lambda mm: 'Xin chào shop' in (mm.body or '')))

    def test_inbound_reuses_open_ticket(self):
        t1 = self.account._handle_inbound('u2', 'lần 1')
        t2 = self.account._handle_inbound('u2', 'lần 2')
        self.assertEqual(t1, t2, 'tin tiếp theo cùng người → cùng ticket đang mở')

    # ---- gửi ra ----
    def _conv_with_ticket(self, uid='u9'):
        conv = self.env['vct.zalo.conversation']._get_or_create(self.account, uid, 'Khách 9')
        conv._ensure_ticket()
        return conv

    def test_agent_reply_sends_to_zalo(self):
        conv = self._conv_with_ticket('u9')
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            conv.ticket_id.message_post(
                body='<p>Chào anh, đơn đang giao ạ</p>',
                message_type='comment', subtype_xmlid='mail.mt_comment')
        m.assert_called_once()
        payload = m.call_args.kwargs['json_body']
        self.assertEqual(payload['recipient']['user_id'], 'u9')
        self.assertIn('Chào anh', payload['message']['text'])

    def test_internal_note_not_sent(self):
        conv = self._conv_with_ticket('u10')
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            conv.ticket_id.message_post(
                body='ghi chú nội bộ', message_type='comment', subtype_xmlid='mail.mt_note')
        m.assert_not_called()

    def test_send_message_ok(self):
        with patch.object(self.acc_cls, '_http_post', return_value=_Resp()) as m:
            ok = self.account._send_message('uX', 'test')
        self.assertTrue(ok)
        m.assert_called_once()

    # ---- chữ ký webhook ----
    def test_signature_valid_and_invalid(self):
        raw = b'{"event_name":"user_send_text","timestamp":"1700000000"}'
        good = 'mac=' + hashlib.sha256(
            (self.account.app_id + raw.decode() + '1700000000' + self.account.secret_key).encode()
        ).hexdigest()
        self.assertTrue(self.account._verify_signature(raw, good, '1700000000'))
        self.assertFalse(self.account._verify_signature(raw, 'mac=sai', '1700000000'))

    def test_signature_skipped_without_secret(self):
        acc = self.env['vct.zalo.account'].create({'name': 'no secret', 'oa_id': 'OA9'})
        self.assertTrue(acc._verify_signature(b'{}', None, None), 'không có secret → bỏ qua verify')
