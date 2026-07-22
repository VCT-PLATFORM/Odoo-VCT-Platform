# Written for VCT Platform. Not part of Odoo S.A.
import hashlib
import logging

import httpx

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

SEND_URL = 'https://openapi.zalo.me/v3.0/oa/message/cs'
OAUTH_URL = 'https://oauth.zaloapp.com/v4/oa/access_token'


class VctZaloAccount(models.Model):
    """Một Zalo Official Account. Giữ token (credential do người dùng nhập) và là
    cổng vào/ra cho kênh Zalo. Không lưu hội thoại ở đây — hội thoại nằm ở chatter
    của ticket (tái dùng mail.thread)."""
    _name = 'vct.zalo.account'
    _description = 'Tài khoản Zalo OA'

    name = fields.Char('Tên', required=True)
    oa_id = fields.Char('OA ID', required=True, help='ID của Official Account (khớp payload webhook).')
    app_id = fields.Char('App ID')
    access_token = fields.Char('Access Token', password=True, help='Do bạn nhập từ Zalo. Hết hạn ~1 ngày.')
    refresh_token = fields.Char('Refresh Token', password=True, help='Dùng để tự gia hạn access token.')
    secret_key = fields.Char('App Secret Key', password=True, help='Để xác thực chữ ký webhook + gia hạn token.')
    token_expiry = fields.Datetime('Token hết hạn lúc')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    default_team_id = fields.Many2one(
        'helpdesk.team', string='Đội xử lý', help='Ticket sinh từ OA này vào đội hỗ trợ này.')
    conversation_count = fields.Integer(compute='_compute_conversation_count')

    _oa_id_uniq = models.Constraint('UNIQUE(oa_id)', 'Mỗi OA ID chỉ khai báo một lần.')

    def _compute_conversation_count(self):
        counts = dict(self.env['vct.zalo.conversation']._read_group(
            [('account_id', 'in', self.ids)], groupby=['account_id'], aggregates=['__count']))
        for acc in self:
            acc.conversation_count = counts.get(acc, 0)

    # ---- HTTP (tách riêng để test mock) ----
    def _http_post(self, url, headers=None, json_body=None, data=None):
        with httpx.Client(timeout=15) as client:
            return client.post(url, headers=headers or {}, json=json_body, data=data)

    # ---- Gửi ra Zalo ----
    def _send_message(self, zalo_user_id, text):
        """Gửi text tới người dùng Zalo. Không raise ra ngoài — lỗi chỉ log, để không
        làm hỏng thao tác đăng bài của agent. ponytail: đồng bộ; đưa vào hàng đợi nếu chặn."""
        self.ensure_one()
        if not self.access_token:
            _logger.warning('Zalo %s: chưa có access_token, bỏ gửi', self.name)
            return False
        payload = {'recipient': {'user_id': zalo_user_id}, 'message': {'text': (text or '')[:2000]}}
        try:
            resp = self._http_post(SEND_URL, headers={'access_token': self.access_token}, json_body=payload)
            body = resp.json() if resp.content else {}
            if body.get('error') not in (0, None):
                _logger.warning('Zalo gửi lỗi (%s): %s', self.name, body)
                return False
            return True
        except Exception as e:
            _logger.exception('Zalo %s: lỗi gửi tin: %s', self.name, e)
            return False

    # ---- Gia hạn token (chạy live; cron gọi) ----
    def _refresh_token(self):
        for acc in self.filtered(lambda a: a.refresh_token and a.app_id and a.secret_key):
            try:
                resp = acc._http_post(
                    OAUTH_URL, headers={'secret_key': acc.secret_key},
                    data={'app_id': acc.app_id, 'grant_type': 'refresh_token',
                          'refresh_token': acc.refresh_token})
                body = resp.json() if resp.content else {}
                if body.get('access_token'):
                    acc.write({
                        'access_token': body['access_token'],
                        'refresh_token': body.get('refresh_token') or acc.refresh_token,
                    })
                    _logger.info('Zalo %s: đã gia hạn access_token', acc.name)
            except Exception:
                _logger.exception('Zalo %s: gia hạn token lỗi', acc.name)

    def _cron_refresh_tokens(self):
        self.search([('active', '=', True)])._refresh_token()

    # ---- Xác thực chữ ký webhook ----
    def _verify_signature(self, raw_body, mac_header, timestamp):
        """Zalo: mac = sha256(appId + data + timestamp + OASecretKey). Không cấu hình
        secret → chấp nhận (chế độ dev) + cảnh báo."""
        self.ensure_one()
        if not self.secret_key:
            _logger.warning('Zalo %s: chưa cấu hình secret_key, bỏ qua verify chữ ký', self.name)
            return True
        data = raw_body.decode() if isinstance(raw_body, bytes) else (raw_body or '')
        expected = hashlib.sha256(
            f'{self.app_id or ""}{data}{timestamp or ""}{self.secret_key}'.encode()).hexdigest()
        return (mac_header or '').replace('mac=', '') == expected

    # ---- Nhận tin vào ----
    def _handle_inbound(self, zalo_user_id, text, display_name=None):
        """Tin nhắn khách → tìm/tạo hội thoại + ticket, ghi vào chatter ticket."""
        self.ensure_one()
        conv = self.env['vct.zalo.conversation']._get_or_create(self, zalo_user_id, display_name)
        ticket = conv._ensure_ticket()
        ticket.with_context(zalo_inbound=True).message_post(
            body=text or '', author_id=conv.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')
        conv.last_message_at = fields.Datetime.now()
        return ticket

    def action_view_conversations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Hội thoại Zalo'),
            'res_model': 'vct.zalo.conversation', 'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
        }
