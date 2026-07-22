# Written for VCT Platform. Not part of Odoo S.A.
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class VctZaloController(http.Controller):

    @http.route('/vct_zalo/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def zalo_webhook(self, **kw):
        """Nhận sự kiện Zalo OA. Luôn trả 200 (Zalo retry nếu khác 200)."""
        raw = request.httprequest.get_data()
        try:
            data = json.loads(raw or b'{}')
        except Exception:
            return request.make_response('bad json', status=200)

        oa_id = (data.get('recipient') or {}).get('id') or data.get('oa_id')
        account = request.env['vct.zalo.account'].sudo().search(
            [('oa_id', '=', str(oa_id))], limit=1)
        if not account:
            _logger.warning('Zalo webhook: không tìm thấy OA %s', oa_id)
            return request.make_response('ok', status=200)

        mac = request.httprequest.headers.get('X-ZEvent-Signature')
        if not account._verify_signature(raw, mac, data.get('timestamp')):
            _logger.warning('Zalo webhook: chữ ký không hợp lệ cho OA %s', oa_id)
            return request.make_response('ok', status=200)

        if data.get('event_name') == 'user_send_text':
            sender = (data.get('sender') or {}).get('id')
            text = (data.get('message') or {}).get('text')
            if sender:
                try:
                    account._handle_inbound(sender, text)
                except Exception:
                    _logger.exception('Zalo webhook: xử lý tin lỗi (OA %s)', oa_id)
        return request.make_response('ok', status=200)
