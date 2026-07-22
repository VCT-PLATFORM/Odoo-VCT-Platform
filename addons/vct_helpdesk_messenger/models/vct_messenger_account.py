# Written for VCT Platform. Not part of Odoo S.A.
import hashlib
import hmac
import logging

import httpx

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

SEND_URL = 'https://graph.facebook.com/v20.0/me/messages'


class VctMessengerAccount(models.Model):
    """Một Facebook Page (Messenger). Cùng mô hình với Zalo: token là credential do
    người dùng nhập; hội thoại nằm ở chatter ticket."""
    _name = 'vct.messenger.account'
    _description = 'Tài khoản Facebook Messenger'

    name = fields.Char('Tên', required=True)
    page_id = fields.Char('Page ID', required=True, help='ID Fanpage (khớp entry.id của webhook).')
    page_access_token = fields.Char('Page Access Token', password=True)
    app_secret = fields.Char('App Secret', password=True, help='Để xác thực chữ ký X-Hub-Signature-256.')
    verify_token = fields.Char('Verify Token', help='Chuỗi bạn tự đặt, khớp lúc đăng ký webhook.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    default_team_id = fields.Many2one('helpdesk.team', string='Đội xử lý')
    conversation_count = fields.Integer(compute='_compute_conversation_count')

    _page_uniq = models.Constraint('UNIQUE(page_id)', 'Mỗi Page ID chỉ khai báo một lần.')

    def _compute_conversation_count(self):
        counts = dict(self.env['vct.messenger.conversation']._read_group(
            [('account_id', 'in', self.ids)], groupby=['account_id'], aggregates=['__count']))
        for acc in self:
            acc.conversation_count = counts.get(acc, 0)

    def _http_post(self, url, json_body=None, params=None):
        with httpx.Client(timeout=15) as client:
            return client.post(url, json=json_body, params=params or {})

    def _send_message(self, psid, text):
        """Gửi text tới người dùng Messenger. Lỗi chỉ log, không raise."""
        self.ensure_one()
        if not self.page_access_token:
            _logger.warning('Messenger %s: chưa có page token, bỏ gửi', self.name)
            return False
        payload = {'recipient': {'id': psid}, 'messaging_type': 'RESPONSE',
                   'message': {'text': (text or '')[:2000]}}
        try:
            resp = self._http_post(SEND_URL, json_body=payload,
                                   params={'access_token': self.page_access_token})
            body = resp.json() if resp.content else {}
            if body.get('error'):
                _logger.warning('Messenger gửi lỗi (%s): %s', self.name, body)
                return False
            return True
        except Exception as e:
            _logger.exception('Messenger %s: lỗi gửi tin: %s', self.name, e)
            return False

    def _verify_signature(self, raw_body, sig_header):
        """FB: X-Hub-Signature-256 = 'sha256=' + hmac_sha256(app_secret, body).
        Không cấu hình app_secret → chấp nhận (dev) + cảnh báo."""
        self.ensure_one()
        if not self.app_secret:
            _logger.warning('Messenger %s: chưa có app_secret, bỏ qua verify chữ ký', self.name)
            return True
        if not sig_header or 'sha256=' not in sig_header:
            return False
        body = raw_body if isinstance(raw_body, bytes) else (raw_body or '').encode()
        expected = hmac.new(self.app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig_header.split('sha256=', 1)[1], expected)

    def _handle_inbound(self, psid, text, display_name=None):
        self.ensure_one()
        conv = self.env['vct.messenger.conversation']._get_or_create(self, psid, display_name)
        ticket = conv._ensure_ticket()
        ticket.with_context(messenger_inbound=True).message_post(
            body=text or '', author_id=conv.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')
        conv.last_message_at = fields.Datetime.now()
        return ticket

    def action_view_conversations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Hội thoại Messenger'),
            'res_model': 'vct.messenger.conversation', 'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
        }
