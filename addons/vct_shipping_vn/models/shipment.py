# Written for VCT Platform. Not part of Odoo S.A.
import logging

import httpx

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_DEFAULT_URL = {
    'ghn': 'https://online-gateway.ghn.vn',
    'ghtk': 'https://services.giaohangtietkiem.vn',
    'viettelpost': 'https://partner.viettelpost.vn',
}


class Shipment(models.Model):
    """Vận đơn gửi qua nhà vận chuyển VN. Tạo đơn → gọi API hãng → lưu mã vận đơn +
    phí. Adapter theo từng hãng; HTTP tách ở `_http_request` để test mock được."""
    _name = 'vct.shipment'
    _description = 'Vận đơn'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char('Mã nội bộ', required=True, default=lambda self: _('Mới'), copy=False)
    sale_order_id = fields.Many2one('sale.order', string='Đơn bán', ondelete='set null')
    carrier_id = fields.Many2one('vct.shipping.carrier', string='Nhà vận chuyển', required=True)
    partner_id = fields.Many2one('res.partner', string='Người nhận')
    to_name = fields.Char('Tên người nhận')
    to_phone = fields.Char('SĐT nhận')
    to_address = fields.Char('Địa chỉ nhận')
    to_district_id = fields.Char('Mã quận/huyện', help='GHN: to_district_id (số).')
    to_ward_code = fields.Char('Mã phường/xã', help='GHN: to_ward_code.')
    weight = fields.Integer('Khối lượng (gram)', default=500)
    cod_amount = fields.Monetary('Thu hộ (COD)', currency_field='currency_id')
    fee = fields.Monetary('Phí ship', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    tracking_code = fields.Char('Mã vận đơn', readonly=True, copy=False, tracking=True)
    state = fields.Selection([
        ('draft', 'Nháp'), ('created', 'Đã tạo vận đơn'), ('delivering', 'Đang giao'),
        ('delivered', 'Đã giao'), ('returned', 'Hoàn'), ('cancel', 'Đã huỷ'),
    ], default='draft', tracking=True, string='Trạng thái')
    raw_response = fields.Text('Phản hồi hãng', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vct.shipment') or _('Mới')
        return super().create(vals_list)

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.partner_id:
            self.to_name = self.partner_id.name
            self.to_phone = self.partner_id.phone or self.partner_id.mobile
            self.to_address = ', '.join(filter(None, [
                self.partner_id.street, self.partner_id.city]))

    def _base_url(self):
        self.ensure_one()
        return (self.carrier_id.base_url or _DEFAULT_URL.get(self.carrier_id.provider, '')).rstrip('/')

    def _http_request(self, method, url, headers=None, json_body=None):
        """Một lần gọi HTTP. Tách riêng để test mock."""
        with httpx.Client(timeout=20) as client:
            return client.request(method, url, headers=headers or {}, json=json_body)

    # ---- Hành động ----
    def action_create_shipment(self):
        for ship in self:
            if ship.state != 'draft':
                continue
            if not ship.carrier_id.token:
                raise UserError(_('Nhà vận chuyển chưa có API Token.'))
            method = getattr(ship, '_provider_%s_create' % ship.carrier_id.provider, None)
            if not method:
                raise UserError(_('Chưa hỗ trợ nhà vận chuyển này.'))
            try:
                result = method()
            except UserError:
                raise
            except Exception as e:
                _logger.exception('Tạo vận đơn lỗi')
                raise UserError(_('Gọi hãng vận chuyển lỗi: %s', e))
            ship.write({
                'tracking_code': result.get('tracking_code'),
                'fee': result.get('fee') or 0.0,
                'raw_response': result.get('raw'),
                'state': 'created',
            })
            ship.message_post(body=_('Đã tạo vận đơn %s (phí %s).',
                                     result.get('tracking_code'), result.get('fee')))

    def action_cancel(self):
        self.write({'state': 'cancel'})

    # ---- Adapter GHN ----
    def _provider_ghn_create(self):
        self.ensure_one()
        carrier = self.carrier_id
        url = self._base_url() + '/shiip/public-api/v2/shipping-order/create'
        payload = {
            'to_name': self.to_name, 'to_phone': self.to_phone,
            'to_address': self.to_address, 'to_district_id': self.to_district_id and int(self.to_district_id) or 0,
            'to_ward_code': self.to_ward_code or '',
            'weight': self.weight or 500, 'cod_amount': int(self.cod_amount or 0),
            'service_type_id': 2, 'payment_type_id': 1, 'required_note': 'CHOXEMHANGKHONGTHU',
            'items': [{'name': self.name, 'quantity': 1, 'weight': self.weight or 500}],
        }
        resp = self._http_request('POST', url, headers={
            'Token': carrier.token, 'ShopId': carrier.shop_id or '', 'Content-Type': 'application/json',
        }, json_body=payload)
        data = resp.json()
        d = data.get('data') or {}
        if not d.get('order_code'):
            raise UserError(_('GHN từ chối: %s', data.get('message') or data))
        return {'tracking_code': d.get('order_code'), 'fee': d.get('total_fee'), 'raw': str(data)[:2000]}

    # ---- Adapter GHTK ----
    def _provider_ghtk_create(self):
        self.ensure_one()
        carrier = self.carrier_id
        url = self._base_url() + '/services/shipment/order'
        payload = {
            'products': [{'name': self.name, 'weight': (self.weight or 500) / 1000.0, 'quantity': 1}],
            'order': {
                'id': self.name, 'name': self.to_name, 'tel': self.to_phone,
                'address': self.to_address, 'pick_money': int(self.cod_amount or 0),
                'value': int(self.cod_amount or 0), 'weight': (self.weight or 500) / 1000.0,
            },
        }
        resp = self._http_request('POST', url, headers={
            'Token': carrier.token, 'Content-Type': 'application/json',
        }, json_body=payload)
        data = resp.json()
        if not data.get('success'):
            raise UserError(_('GHTK từ chối: %s', data.get('message') or data))
        order = data.get('order') or {}
        return {'tracking_code': order.get('label'), 'fee': order.get('fee'), 'raw': str(data)[:2000]}

    # ---- Adapter ViettelPost ----
    def _provider_viettelpost_create(self):
        self.ensure_one()
        carrier = self.carrier_id
        url = self._base_url() + '/v2/order/createOrder'
        payload = {
            'ORDER_NUMBER': self.name, 'RECEIVER_FULLNAME': self.to_name,
            'RECEIVER_ADDRESS': self.to_address, 'RECEIVER_PHONE': self.to_phone,
            'PRODUCT_WEIGHT': self.weight or 500, 'MONEY_COLLECTION': int(self.cod_amount or 0),
            'PRODUCT_NAME': self.name, 'PRODUCT_QUANTITY': 1,
        }
        resp = self._http_request('POST', url, headers={
            'Token': carrier.token, 'Content-Type': 'application/json',
        }, json_body=payload)
        data = resp.json()
        d = data.get('data') or {}
        if not d.get('ORDER_NUMBER'):
            raise UserError(_('ViettelPost từ chối: %s', data.get('message') or data))
        return {'tracking_code': d.get('ORDER_NUMBER'), 'fee': d.get('MONEY_TOTAL_FEE'),
                'raw': str(data)[:2000]}
