# Written for VCT Platform. Not part of Odoo S.A.
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class VctMessengerController(http.Controller):

    @http.route('/vct_messenger/webhook', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def messenger_webhook(self, **kw):
        # GET: Facebook xác minh webhook bằng verify_token
        if request.httprequest.method == 'GET':
            token = kw.get('hub.verify_token')
            challenge = kw.get('hub.challenge')
            account = request.env['vct.messenger.account'].sudo().search(
                [('verify_token', '=', token)], limit=1)
            if kw.get('hub.mode') == 'subscribe' and account:
                return request.make_response(challenge or '')
            return request.make_response('forbidden', status=403)

        # POST: sự kiện tin nhắn
        raw = request.httprequest.get_data()
        sig = request.httprequest.headers.get('X-Hub-Signature-256')
        try:
            data = json.loads(raw or b'{}')
        except Exception:
            return request.make_response('EVENT_RECEIVED', status=200)

        Account = request.env['vct.messenger.account'].sudo()
        for entry in data.get('entry', []):
            account = Account.search([('page_id', '=', str(entry.get('id')))], limit=1)
            if not account or not account._verify_signature(raw, sig):
                continue
            for msg in entry.get('messaging', []):
                psid = (msg.get('sender') or {}).get('id')
                text = (msg.get('message') or {}).get('text')
                if psid and text:
                    try:
                        account._handle_inbound(psid, text)
                    except Exception:
                        _logger.exception('Messenger webhook: xử lý tin lỗi (page %s)', entry.get('id'))
        return request.make_response('EVENT_RECEIVED', status=200)
