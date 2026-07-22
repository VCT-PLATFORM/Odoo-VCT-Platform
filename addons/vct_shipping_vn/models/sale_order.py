# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipment_ids = fields.One2many('vct.shipment', 'sale_order_id', string='Vận đơn')
    shipment_count = fields.Integer(compute='_compute_shipment_count')

    def _compute_shipment_count(self):
        counts = dict(self.env['vct.shipment']._read_group(
            [('sale_order_id', 'in', self.ids)], groupby=['sale_order_id'], aggregates=['__count']))
        for order in self:
            order.shipment_count = counts.get(order, 0)

    def action_create_shipment(self):
        self.ensure_one()
        partner = self.partner_shipping_id or self.partner_id
        carrier = self.env['vct.shipping.carrier'].search([('active', '=', True)], limit=1)
        weight_g = int(sum(
            (line.product_id.weight or 0) * line.product_uom_qty for line in self.order_line) * 1000) or 500
        shipment = self.env['vct.shipment'].create({
            'sale_order_id': self.id,
            'carrier_id': carrier.id if carrier else False,
            'partner_id': partner.id,
            'to_name': partner.name,
            'to_phone': partner.phone or partner.mobile,
            'to_address': ', '.join(filter(None, [partner.street, partner.city])),
            'cod_amount': self.amount_total,
            'weight': weight_g,
        })
        return {
            'type': 'ir.actions.act_window', 'name': _('Vận đơn'),
            'res_model': 'vct.shipment', 'res_id': shipment.id, 'view_mode': 'form',
        }

    def action_view_shipments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Vận đơn'),
            'res_model': 'vct.shipment', 'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
        }
