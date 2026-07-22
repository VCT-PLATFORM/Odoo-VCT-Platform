# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, fields, models
from odoo.exceptions import UserError


class SocialShareWizard(models.TransientModel):
    """Chọn sản phẩm từ một hội thoại → gửi thẻ sản phẩm (tên/giá/mô tả) thẳng cho
    khách qua kênh của hội thoại đó."""
    _name = 'vct.social.share.wizard'
    _description = 'Chia sẻ sản phẩm vào chat'

    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    product_ids = fields.Many2many(
        'product.product', string='Sản phẩm', domain="[('sale_ok','=',True)]")
    include_price = fields.Boolean('Kèm giá', default=True)
    custom_message = fields.Text('Lời nhắn thêm')

    def _open_for(self, conversation):
        wiz = self.create({'res_model': conversation._name, 'res_id': conversation.id})
        return {
            'type': 'ir.actions.act_window', 'name': _('Chia sẻ sản phẩm'),
            'res_model': 'vct.social.share.wizard', 'res_id': wiz.id,
            'view_mode': 'form', 'target': 'new',
        }

    def _conversation(self):
        self.ensure_one()
        if self.res_model and self.res_id and self.res_model in self.env:
            return self.env[self.res_model].browse(self.res_id).exists()
        return None

    def _format_card(self, product):
        self.ensure_one()
        lines = ['🛍️ %s' % product.display_name]
        if self.include_price:
            symbol = product.currency_id.symbol or 'đ'
            lines.append(_('Giá: %(price)s %(cur)s',
                           price='{:,.0f}'.format(product.list_price), cur=symbol))
        if product.description_sale:
            lines.append(product.description_sale)
        return '\n'.join(lines)

    def action_share(self):
        self.ensure_one()
        conv = self._conversation()
        if not conv:
            raise UserError(_('Không tìm thấy hội thoại nguồn.'))
        if not self.product_ids:
            raise UserError(_('Chọn ít nhất một sản phẩm để chia sẻ.'))
        for product in self.product_ids:
            conv._send_text(self._format_card(product))
        if self.custom_message:
            conv._send_text(self.custom_message)
        if conv.ticket_id:
            conv.ticket_id.message_post(
                body=_('Đã chia sẻ %s sản phẩm cho khách qua chat.', len(self.product_ids)),
                subtype_xmlid='mail.mt_note')
        return {'type': 'ir.actions.act_window_close'}
