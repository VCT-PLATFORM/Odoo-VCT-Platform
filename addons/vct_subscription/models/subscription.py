# Written for VCT Platform. Not part of Odoo S.A.
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_UNIT_DELTA = {'week': 'weeks', 'month': 'months', 'year': 'years'}


class Subscription(models.Model):
    """Hợp đồng thuê bao: khách + gói định kỳ + các dòng sản phẩm. Cron sinh hoá đơn
    mỗi chu kỳ. Xây trên account.move (không dựng lại hoá đơn)."""
    _name = 'vct.subscription'
    _description = 'Thuê bao'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char('Số thuê bao', required=True, default=lambda self: _('Mới'), copy=False)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True, tracking=True)
    plan_id = fields.Many2one('vct.subscription.plan', string='Gói', required=True, tracking=True)
    date_start = fields.Date('Ngày bắt đầu', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Nháp'), ('progress', 'Đang chạy'), ('paused', 'Tạm dừng'), ('closed', 'Đã đóng'),
    ], default='draft', tracking=True, string='Trạng thái')
    line_ids = fields.One2many('vct.subscription.line', 'subscription_id', string='Dòng', copy=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    next_invoice_date = fields.Date('Hoá đơn kế tiếp', tracking=True)
    recurring_total = fields.Monetary('Tổng mỗi kỳ', compute='_compute_totals', store=True)
    mrr = fields.Monetary('Doanh thu định kỳ/tháng (MRR)', compute='_compute_totals', store=True)
    invoice_ids = fields.One2many('account.move', 'vct_subscription_id', string='Hoá đơn')
    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.depends('line_ids.price_subtotal', 'plan_id')
    def _compute_totals(self):
        for sub in self:
            total = sum(sub.line_ids.mapped('price_subtotal'))
            sub.recurring_total = total
            months = sub.plan_id._period_in_months() if sub.plan_id else 1.0
            sub.mrr = total / months if months else total

    def _compute_invoice_count(self):
        counts = dict(self.env['account.move']._read_group(
            [('vct_subscription_id', 'in', self.ids)], groupby=['vct_subscription_id'],
            aggregates=['__count']))
        for sub in self:
            sub.invoice_count = counts.get(sub, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vct.subscription') or _('Mới')
        return super().create(vals_list)

    # ---- Vòng đời ----
    def action_start(self):
        for sub in self.filtered(lambda s: s.state in ('draft', 'paused')):
            if not sub.line_ids:
                raise UserError(_('Thêm ít nhất một dòng sản phẩm trước khi chạy.'))
            if not sub.next_invoice_date:
                sub.next_invoice_date = sub.date_start or fields.Date.context_today(sub)
            sub.state = 'progress'

    def action_pause(self):
        self.filtered(lambda s: s.state == 'progress').write({'state': 'paused'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.filtered(lambda s: s.state == 'closed').write({'state': 'draft'})

    # ---- Hoá đơn ----
    def _prepare_invoice_lines(self):
        self.ensure_one()
        return [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.name or line.product_id.display_name,
            'quantity': line.quantity,
            'price_unit': line.price_unit,
        }) for line in self.line_ids]

    def _create_invoice(self):
        self.ensure_one()
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'journal_id': journal.id if journal else False,
            'vct_subscription_id': self.id,
            'invoice_line_ids': self._prepare_invoice_lines(),
        })
        return move

    def action_create_invoice(self):
        self.ensure_one()
        move = self._create_invoice()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': move.id, 'view_mode': 'form',
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Hoá đơn'),
            'res_model': 'account.move', 'view_mode': 'list,form',
            'domain': [('vct_subscription_id', '=', self.id)],
        }

    @api.model
    def _cron_generate_invoices(self):
        today = fields.Date.context_today(self)
        due = self.search([('state', '=', 'progress'), ('next_invoice_date', '<=', today)])
        for sub in due:
            try:
                with self.env.cr.savepoint():
                    sub._create_invoice()
                    delta = relativedelta(**{_UNIT_DELTA[sub.plan_id.period_unit]: sub.plan_id.period_value})
                    sub.next_invoice_date = (sub.next_invoice_date or today) + delta
            except Exception:
                _logger.exception('Thuê bao %s: sinh hoá đơn lỗi', sub.name)


class SubscriptionLine(models.Model):
    _name = 'vct.subscription.line'
    _description = 'Dòng thuê bao'

    subscription_id = fields.Many2one('vct.subscription', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    name = fields.Char('Mô tả')
    quantity = fields.Float('Số lượng', default=1.0)
    price_unit = fields.Float('Đơn giá')
    currency_id = fields.Many2one(related='subscription_id.currency_id')
    price_subtotal = fields.Monetary('Thành tiền', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.price_unit = self.product_id.list_price
