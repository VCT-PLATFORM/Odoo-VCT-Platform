# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models


class VctMessengerConversation(models.Model):
    """Ánh xạ người dùng Messenger (PSID) ↔ partner ↔ ticket. Nội dung ở chatter ticket."""
    _name = 'vct.messenger.conversation'
    _description = 'Hội thoại Messenger'
    _order = 'last_message_at desc, id desc'

    name = fields.Char('Tên', compute='_compute_name', store=True)
    account_id = fields.Many2one('vct.messenger.account', required=True, ondelete='cascade', index=True)
    psid = fields.Char('PSID', required=True, index=True, help='Page-Scoped User ID của Facebook.')
    partner_id = fields.Many2one('res.partner', string='Khách hàng')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket hiện tại')
    state = fields.Selection([
        ('bot', 'Bot đang xử lý'), ('human', 'Nhân viên xử lý'), ('closed', 'Đã đóng'),
    ], default='human', required=True)
    last_message_at = fields.Datetime('Tin gần nhất')

    _psid_uniq = models.Constraint(
        'UNIQUE(account_id, psid)', 'Mỗi PSID chỉ một hội thoại trên mỗi Page.')

    @api.depends('partner_id', 'psid')
    def _compute_name(self):
        for conv in self:
            conv.name = conv.partner_id.display_name or _('FB %s', conv.psid or '?')

    def _get_or_create(self, account, psid, display_name=None):
        conv = self.search([('account_id', '=', account.id), ('psid', '=', psid)], limit=1)
        if conv:
            return conv
        partner = self.env['res.partner'].create({
            'name': display_name or _('Khách FB %s', psid),
            'comment': _('Tạo tự động từ Facebook Page %s (PSID %s)', account.name, psid),
        })
        return self.create({
            'account_id': account.id, 'psid': psid, 'partner_id': partner.id, 'state': 'human'})

    def _ensure_ticket(self):
        self.ensure_one()
        if self.ticket_id and not self.ticket_id.stage_id.fold:
            return self.ticket_id
        team = self.account_id.default_team_id
        ticket = self.env['helpdesk.ticket'].create({
            'name': _('Messenger: %s', self.partner_id.display_name),
            'partner_id': self.partner_id.id, 'team_id': team.id if team else False})
        self.ticket_id = ticket
        return ticket

    def action_open_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id, 'view_mode': 'form'}
