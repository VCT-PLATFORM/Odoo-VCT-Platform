# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SocialOrderWizard(models.TransientModel):
    """Chốt đơn nhanh từ một hội thoại: chọn sản phẩm → tạo đơn bán (sale.order)
    cho khách của hội thoại. Đây là thao tác cốt lõi kiểu Pancake."""
    _name = 'vct.social.order.wizard'
    _description = 'Chốt đơn từ hội thoại'

    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True)
    source = fields.Char('Nguồn hội thoại', readonly=True)
    delivery_note = fields.Char('Địa chỉ / Ghi chú giao hàng')
    line_ids = fields.One2many('vct.social.order.wizard.line', 'wizard_id', string='Sản phẩm')

    def _open_for(self, partner, source):
        wiz = self.create({'partner_id': partner.id if partner else False, 'source': source})
        return {
            'type': 'ir.actions.act_window', 'name': _('Chốt đơn từ hội thoại'),
            'res_model': 'vct.social.order.wizard', 'res_id': wiz.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_create_order(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Thêm ít nhất một sản phẩm để chốt đơn.'))
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'origin': self.source,
            'social_source': self.source or _('Mạng xã hội'),
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.price_unit,
            }) for line in self.line_ids],
        })
        if self.delivery_note:
            order.message_post(body=_('Giao hàng: %s', self.delivery_note))
        return {
            'type': 'ir.actions.act_window', 'name': _('Đơn bán'),
            'res_model': 'sale.order', 'res_id': order.id, 'view_mode': 'form',
        }


class SocialOrderWizardLine(models.TransientModel):
    _name = 'vct.social.order.wizard.line'
    _description = 'Dòng chốt đơn'

    wizard_id = fields.Many2one('vct.social.order.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    quantity = fields.Float('Số lượng', default=1.0)
    price_unit = fields.Float('Đơn giá')

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.price_unit = self.product_id.list_price
