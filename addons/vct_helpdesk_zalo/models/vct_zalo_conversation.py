# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models


class VctZaloConversation(models.Model):
    """Ánh xạ một người dùng Zalo ↔ partner ↔ ticket đang mở. Là 'sổ địa chỉ' của
    kênh; nội dung hội thoại vẫn nằm ở chatter của ticket."""
    _name = 'vct.zalo.conversation'
    _description = 'Hội thoại Zalo'
    _order = 'last_message_at desc, id desc'

    name = fields.Char('Tên', compute='_compute_name', store=True)
    account_id = fields.Many2one('vct.zalo.account', required=True, ondelete='cascade', index=True)
    zalo_user_id = fields.Char('Zalo User ID', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket hiện tại')
    state = fields.Selection([
        ('bot', 'Bot đang xử lý'), ('human', 'Nhân viên xử lý'), ('closed', 'Đã đóng'),
    ], default='human', required=True)
    last_message_at = fields.Datetime('Tin gần nhất')

    _user_uniq = models.Constraint(
        'UNIQUE(account_id, zalo_user_id)', 'Mỗi người dùng Zalo chỉ một hội thoại trên mỗi OA.')

    @api.depends('partner_id', 'zalo_user_id')
    def _compute_name(self):
        for conv in self:
            conv.name = conv.partner_id.display_name or _('Zalo %s', conv.zalo_user_id or '?')

    def _get_or_create(self, account, zalo_user_id, display_name=None):
        conv = self.search([
            ('account_id', '=', account.id), ('zalo_user_id', '=', zalo_user_id)], limit=1)
        if conv:
            return conv
        partner = self.env['res.partner'].create({
            'name': display_name or _('Khách Zalo %s', zalo_user_id),
            'comment': _('Tạo tự động từ Zalo OA %s (uid %s)', account.name, zalo_user_id),
        })
        return self.create({
            'account_id': account.id, 'zalo_user_id': zalo_user_id,
            'partner_id': partner.id, 'state': 'human',
        })

    def _ensure_ticket(self):
        """Ticket đang mở của hội thoại, hoặc tạo mới. 'Mở' = chưa ở stage folded (đóng)."""
        self.ensure_one()
        if self.ticket_id and not self.ticket_id.stage_id.fold:
            return self.ticket_id
        team = self.account_id.default_team_id
        ticket = self.env['helpdesk.ticket'].create({
            'name': _('Zalo: %s', self.partner_id.display_name),
            'partner_id': self.partner_id.id,
            'team_id': team.id if team else False,
        })
        self.ticket_id = ticket
        return ticket

    def action_open_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id, 'view_mode': 'form',
        }
