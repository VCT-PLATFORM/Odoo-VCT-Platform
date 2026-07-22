# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import date_utils, float_compare, float_is_zero, float_round


class AccountAsset(models.Model):
    _name = 'account.asset'
    _description = 'Tài sản cố định / Chi phí trả trước'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'acquisition_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Tên', required=True, tracking=True)
    asset_type = fields.Selection([
        ('purchase', 'Tài sản cố định'),
        ('expense', 'Chi phí trả trước'),
    ], string='Loại', required=True, default='purchase', tracking=True,
        help="Cùng cách tính phân bổ, chỉ khác ý nghĩa và tài khoản sử dụng.")
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('open', 'Đang khấu hao'),
        ('close', 'Đã kết thúc'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', required=True, copy=False, tracking=True)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Nhà cung cấp', check_company=True)

    original_value = fields.Monetary(string='Nguyên giá', required=True, tracking=True)
    salvage_value = fields.Monetary(
        string='Giá trị thanh lý', tracking=True,
        help="Phần giá trị không khấu hao, còn lại khi hết thời gian sử dụng.")
    acquisition_date = fields.Date(
        string='Ngày đưa vào sử dụng', required=True, tracking=True,
        default=fields.Date.context_today)

    method_number = fields.Integer(
        string='Số kỳ khấu hao', required=True, default=12, tracking=True)
    method_period = fields.Selection([
        ('1', 'Hàng tháng'),
        ('12', 'Hàng năm'),
    ], string='Tần suất', required=True, default='1', tracking=True)

    journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký', required=True, check_company=True,
        domain="[('type', '=', 'general')]", default=lambda self: self._default_journal())
    account_asset_id = fields.Many2one(
        'account.account', string='Tài khoản tài sản', required=True, check_company=True,
        help="Tài khoản ghi nhận nguyên giá. Chỉ dùng để tham chiếu, không sinh bút toán.")
    account_depreciation_id = fields.Many2one(
        'account.account', string='Tài khoản hao mòn luỹ kế', required=True, check_company=True,
        help="Được ghi Có mỗi kỳ khấu hao.")
    account_expense_id = fields.Many2one(
        'account.account', string='Tài khoản chi phí khấu hao', required=True, check_company=True,
        help="Được ghi Nợ mỗi kỳ khấu hao.")

    depreciation_move_ids = fields.One2many(
        'account.move', 'asset_id', string='Bảng khấu hao', copy=False)
    depreciated_value = fields.Monetary(
        string='Đã khấu hao', compute='_compute_values', store=True,
        help="Tổng khấu hao của các bút toán đã vào sổ.")
    book_value = fields.Monetary(
        string='Giá trị còn lại', compute='_compute_values', store=True)
    total_depreciable = fields.Monetary(
        string='Giá trị phải khấu hao', compute='_compute_total_depreciable', store=True)

    _original_value_positive = models.Constraint(
        'CHECK(original_value > 0)',
        'Nguyên giá phải lớn hơn 0.',
    )
    _method_number_positive = models.Constraint(
        'CHECK(method_number > 0)',
        'Số kỳ khấu hao phải lớn hơn 0.',
    )

    @api.model
    def _default_journal(self):
        return self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1)

    @api.constrains('salvage_value', 'original_value')
    def _check_salvage_value(self):
        for asset in self:
            if float_compare(asset.salvage_value, asset.original_value,
                             precision_rounding=asset.currency_id.rounding) > 0:
                raise ValidationError(_("Giá trị thanh lý không được lớn hơn nguyên giá."))

    @api.depends('original_value', 'salvage_value')
    def _compute_total_depreciable(self):
        for asset in self:
            asset.total_depreciable = asset.original_value - asset.salvage_value

    @api.depends('depreciation_move_ids.state', 'depreciation_move_ids.amount_total_signed',
                 'original_value')
    def _compute_values(self):
        for asset in self:
            posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
            depreciated = sum(
                line.debit
                for move in posted
                for line in move.line_ids
                if line.account_id == asset.account_expense_id
            )
            asset.depreciated_value = depreciated
            asset.book_value = asset.original_value - depreciated

    def _depreciation_dates(self):
        """One date per period, always the last day of the period's month."""
        self.ensure_one()
        step = int(self.method_period)
        first = date_utils.end_of(self.acquisition_date, 'month')
        return [
            date_utils.end_of(first + relativedelta(months=step * i), 'month')
            for i in range(self.method_number)
        ]

    def _depreciation_amounts(self):
        """Amount per period; the last one absorbs the rounding so the board
        adds up to the depreciable value exactly."""
        self.ensure_one()
        rounding = self.currency_id.rounding
        per_period = float_round(
            self.total_depreciable / self.method_number, precision_rounding=rounding)
        amounts = [per_period] * self.method_number
        amounts[-1] = float_round(
            self.total_depreciable - per_period * (self.method_number - 1),
            precision_rounding=rounding)
        return amounts

    def _prepare_depreciation_move(self, date, amount, sequence):
        self.ensure_one()
        label = _('%(name)s - kỳ %(n)s/%(total)s',
                  name=self.name, n=sequence, total=self.method_number)
        return {
            'asset_id': self.id,
            'journal_id': self.journal_id.id,
            'date': date,
            'ref': label,
            'company_id': self.company_id.id,
            'line_ids': [
                (0, 0, {
                    'name': label,
                    'account_id': self.account_expense_id.id,
                    'debit': amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                }),
                (0, 0, {
                    'name': label,
                    'account_id': self.account_depreciation_id.id,
                    'debit': 0.0,
                    'credit': amount,
                    'partner_id': self.partner_id.id,
                }),
            ],
        }

    def _build_board(self):
        """(Re)create the depreciation board. Posted entries are kept and their
        periods are not generated again."""
        moves_values = []
        for asset in self:
            posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
            (asset.depreciation_move_ids - posted).filtered(
                lambda m: m.state == 'draft').unlink()
            done = len(posted)
            dates = asset._depreciation_dates()
            amounts = asset._depreciation_amounts()
            for index in range(done, asset.method_number):
                if float_is_zero(amounts[index], precision_rounding=asset.currency_id.rounding):
                    continue
                moves_values.append(
                    asset._prepare_depreciation_move(dates[index], amounts[index], index + 1))
        if moves_values:
            self.env['account.move'].create(moves_values)

    def action_validate(self):
        for asset in self:
            if asset.state != 'draft':
                raise UserError(_("Chỉ tài sản ở trạng thái nháp mới xác nhận được."))
        self._build_board()
        self.state = 'open'

    def action_set_to_draft(self):
        for asset in self:
            if asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted'):
                raise UserError(_(
                    "Không thể đưa về nháp: đã có bút toán khấu hao vào sổ. "
                    "Hãy huỷ vào sổ các bút toán đó trước."))
        self.depreciation_move_ids.unlink()
        self.state = 'draft'

    def action_close(self):
        self.state = 'close'

    def action_cancel(self):
        self.depreciation_move_ids.filtered(lambda m: m.state == 'draft').unlink()
        self.state = 'cancel'

    def action_open_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bút toán khấu hao'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
        }

    @api.model
    def _cron_post_depreciation(self, date=None):
        """Post every due depreciation entry. Returns what it posted so the
        behaviour is testable without waiting for the scheduler."""
        date = date or fields.Date.context_today(self)
        moves = self.env['account.move'].search([
            ('asset_id', '!=', False),
            ('state', '=', 'draft'),
            ('date', '<=', date),
            ('asset_id.state', '=', 'open'),
        ])
        moves.action_post()
        # an asset whose board is fully posted has nothing left to depreciate
        for asset in moves.asset_id:
            if all(m.state == 'posted' for m in asset.depreciation_move_ids):
                asset.state = 'close'
        return moves


class AccountMove(models.Model):
    _inherit = 'account.move'

    asset_id = fields.Many2one(
        'account.asset', string='Tài sản', ondelete='cascade', index='btree_not_null', copy=False)
