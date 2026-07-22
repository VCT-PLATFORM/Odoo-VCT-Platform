# Written for VCT Platform. Not part of Odoo S.A.

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountFollowupLevel(models.Model):
    _name = 'account.followup.level'
    _description = 'Mức nhắc nợ'
    _order = 'delay, id'

    name = fields.Char(string='Tên mức', required=True, translate=True)
    delay = fields.Integer(
        string='Số ngày quá hạn', required=True,
        help="Mức này áp dụng khi hoá đơn đã quá hạn ít nhất số ngày này.")
    template_id = fields.Many2one(
        'mail.template', string='Mẫu email',
        domain=[('model', '=', 'res.partner')],
        help="Bỏ trống thì mức này chỉ nhắc nội bộ, không gửi email cho khách.")
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        help="Bỏ trống để áp dụng cho mọi công ty.")

    _delay_uniq = models.Constraint(
        'unique (delay, company_id)',
        'Đã có mức nhắc nợ với cùng số ngày quá hạn.',
    )

    @api.model
    def _levels_for_company(self):
        return self.search([('company_id', 'in', [self.env.company.id, False])])


class ResPartner(models.Model):
    _inherit = 'res.partner'

    followup_level_id = fields.Many2one(
        'account.followup.level', string='Mức nhắc nợ', compute='_compute_followup',
        help="Mức tương ứng với hoá đơn quá hạn lâu nhất của khách hàng.")
    followup_overdue_amount = fields.Monetary(
        string='Số tiền quá hạn', compute='_compute_followup', currency_field='currency_id')
    followup_next_date = fields.Date(
        string='Ngày nhắc tiếp theo', copy=False,
        help="Bỏ trống nghĩa là có thể nhắc ngay khi có hoá đơn quá hạn.")
    # currency_id comes from account (res.partner._get_company_currency); do not
    # redefine it here: partners usually have no company_id of their own.

    @api.model
    def _overdue_base_domain(self, date=None):
        """Journal items that make a customer overdue: posted, still unmatched
        receivables past their due date."""
        return [
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('date_maturity', '<', date or fields.Date.context_today(self)),
            ('company_id', '=', self.env.company.id),
        ]

    def _overdue_line_domain(self, date=None):
        return [('partner_id', 'in', self.ids)] + self._overdue_base_domain(date)

    @api.depends_context('company')
    def _compute_followup(self):
        levels = self.env['account.followup.level']._levels_for_company()
        self.followup_level_id = False
        self.followup_overdue_amount = 0.0
        if not self.ids:
            return
        today = fields.Date.context_today(self)
        groups = self.env['account.move.line']._read_group(
            self._overdue_line_domain(today),
            ['partner_id'], ['amount_residual:sum', 'date_maturity:min'],
        )
        for partner, residual, oldest in groups:
            days = (today - oldest).days
            matching = levels.filtered(lambda level: level.delay <= days)
            partner.followup_overdue_amount = residual
            partner.followup_level_id = matching[-1] if matching else False

    @api.model
    def _followup_partners_overdue(self, date=None):
        """Customers with a positive overdue balance right now. The figures are
        date-dependent so they cannot be stored, hence no searchable field: the
        set is resolved here and handed to the views as an explicit id list."""
        groups = self.env['account.move.line']._read_group(
            self._overdue_base_domain(date) + [('partner_id', '!=', False)],
            ['partner_id'], ['amount_residual:sum'],
        )
        return self.browse([p.id for p, residual in groups if residual > 0])

    @api.model
    def _followup_partners_to_remind(self, date=None):
        """Overdue, a level reached, and not snoozed."""
        date = date or fields.Date.context_today(self)
        return self._followup_partners_overdue(date).filtered(lambda p: (
            p.followup_level_id
            and (not p.followup_next_date or p.followup_next_date <= date)
        ))

    @api.model
    def action_followup_overview(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nhắc nợ khách hàng'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('account_followup.res_partner_view_list_followup').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('id', 'in', self._followup_partners_overdue().ids)],
            'help': _('<p class="o_view_nocontent_smiling_face">Không có khách hàng nào nợ quá hạn</p>'
                      '<p>Khách hàng xuất hiện ở đây khi có hoá đơn đã vào sổ, chưa đối soát và quá hạn thanh toán.</p>'),
        }

    def action_followup_send(self):
        """Email the customer their overdue statement and snooze to the next level."""
        for partner in self:
            level = partner.followup_level_id
            if not level:
                raise UserError(_(
                    "%s chưa tới mức nhắc nợ nào: không có hoá đơn quá hạn.", partner.display_name))
            if level.template_id:
                level.template_id.send_mail(partner.id, force_send=False)
            partner.message_post(
                body=_("Đã nhắc nợ mức <b>%(level)s</b>, số tiền quá hạn %(amount)s.",
                       level=level.name,
                       amount=partner.currency_id.format(partner.followup_overdue_amount)),
            )
            partner._followup_snooze()
        return True

    def _followup_snooze(self):
        """Wait until the next level is due before reminding again."""
        for partner in self:
            levels = self.env['account.followup.level']._levels_for_company().filtered(
                lambda level: level.delay > partner.followup_level_id.delay)[:1]
            today = fields.Date.context_today(self)
            if levels:
                oldest = min(self.env['account.move.line'].search(
                    partner._overdue_line_domain(today)).mapped('date_maturity'))
                partner.followup_next_date = oldest + relativedelta(days=levels.delay)
            else:
                partner.followup_next_date = today + relativedelta(days=30)

    def action_open_overdue_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoá đơn quá hạn'),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': self._overdue_line_domain(),
        }

    @api.model
    def _cron_send_followup(self, date=None):
        partners = self._followup_partners_to_remind(date)
        for partner in partners:
            partner.action_followup_send()
        return partners
