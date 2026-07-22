# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RentalOrder(models.Model):
    """Đơn cho thuê: khách + kỳ thuê (nhận–trả) + dòng sản phẩm. Giá theo số ngày thuê;
    kiểm trùng lịch để không cho thuê quá số lượng."""
    _name = 'vct.rental.order'
    _description = 'Đơn thuê'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char('Số đơn', required=True, default=lambda self: _('Mới'), copy=False)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True, tracking=True)
    date_start = fields.Datetime('Ngày nhận', required=True,
                                 default=fields.Datetime.now, tracking=True)
    date_return = fields.Datetime('Ngày trả (dự kiến)', required=True, tracking=True)
    date_returned = fields.Datetime('Đã trả lúc', readonly=True)
    state = fields.Selection([
        ('draft', 'Nháp'), ('confirmed', 'Đã đặt'), ('picked_up', 'Đang thuê'),
        ('returned', 'Đã trả'), ('cancel', 'Đã huỷ'),
    ], default='draft', tracking=True, string='Trạng thái')
    line_ids = fields.One2many('vct.rental.order.line', 'order_id', string='Dòng', copy=True)
    duration_days = fields.Integer('Số ngày thuê', compute='_compute_duration', store=True)
    amount_total = fields.Monetary('Tổng tiền', compute='_compute_amount', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    invoice_ids = fields.One2many('account.move', 'vct_rental_order_id', string='Hoá đơn')
    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.depends('date_start', 'date_return')
    def _compute_duration(self):
        for order in self:
            if order.date_start and order.date_return and order.date_return > order.date_start:
                order.duration_days = max(1, (order.date_return - order.date_start).days)
            else:
                order.duration_days = 1

    @api.depends('line_ids.price_subtotal')
    def _compute_amount(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_subtotal'))

    def _compute_invoice_count(self):
        counts = dict(self.env['account.move']._read_group(
            [('vct_rental_order_id', 'in', self.ids)], groupby=['vct_rental_order_id'],
            aggregates=['__count']))
        for order in self:
            order.invoice_count = counts.get(order, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vct.rental.order') or _('Mới')
        return super().create(vals_list)

    # ---- Kiểm trùng lịch ----
    def _check_availability(self):
        for order in self:
            for line in order.line_ids:
                product = line.product_id
                overlapping = self.env['vct.rental.order.line'].search([
                    ('product_id', '=', product.id),
                    ('order_id.state', 'in', ('confirmed', 'picked_up')),
                    ('order_id', '!=', order.id),
                    ('order_id.date_start', '<', order.date_return),
                    ('order_id.date_return', '>', order.date_start),
                ])
                booked = sum(overlapping.mapped('quantity')) + line.quantity
                if booked > (product.rental_stock or 0):
                    raise UserError(_(
                        'Sản phẩm "%(p)s" không đủ để cho thuê trong kỳ này '
                        '(đặt %(b)s > tồn cho thuê %(s)s).',
                        p=product.display_name, b=booked, s=product.rental_stock))

    # ---- Vòng đời ----
    def action_confirm(self):
        for order in self.filtered(lambda o: o.state == 'draft'):
            if not order.line_ids:
                raise UserError(_('Thêm ít nhất một sản phẩm cho thuê.'))
            order._check_availability()
            order.state = 'confirmed'

    def action_pickup(self):
        self.filtered(lambda o: o.state == 'confirmed').write({'state': 'picked_up'})

    def action_return(self):
        for order in self.filtered(lambda o: o.state == 'picked_up'):
            order.write({'state': 'returned', 'date_returned': fields.Datetime.now()})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda o: o.state == 'cancel').write({'state': 'draft'})

    # ---- Hoá đơn ----
    def _create_invoice(self):
        self.ensure_one()
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
        lines = [(0, 0, {
            'product_id': line.product_id.id,
            'name': _('%(p)s — thuê %(d)s ngày', p=line.product_id.display_name, d=self.duration_days),
            'quantity': line.quantity * self.duration_days,
            'price_unit': line.price_day,
        }) for line in self.line_ids]
        return self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner_id.id,
            'invoice_origin': self.name, 'journal_id': journal.id if journal else False,
            'vct_rental_order_id': self.id, 'invoice_line_ids': lines,
        })

    def action_create_invoice(self):
        self.ensure_one()
        move = self._create_invoice()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move',
                'res_id': move.id, 'view_mode': 'form'}

    def action_view_invoices(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Hoá đơn'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('vct_rental_order_id', '=', self.id)]}


class RentalOrderLine(models.Model):
    _name = 'vct.rental.order.line'
    _description = 'Dòng đơn thuê'

    order_id = fields.Many2one('vct.rental.order', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Sản phẩm', required=True, domain="[('rental_ok','=',True)]")
    quantity = fields.Float('Số lượng', default=1.0)
    price_day = fields.Float('Giá thuê/ngày')
    duration_days = fields.Integer(related='order_id.duration_days')
    currency_id = fields.Many2one(related='order_id.currency_id')
    price_subtotal = fields.Monetary('Thành tiền', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_day', 'order_id.duration_days')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_day * (line.order_id.duration_days or 1)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_day = self.product_id.rental_price_day
