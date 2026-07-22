# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, fields, models, tools
from odoo.exceptions import UserError


class SocialThread(models.Model):
    """Inbox hợp nhất: một SQL view UNION mọi hội thoại Zalo + Messenger, để xem/xử lý
    trên một màn hình (kiểu Pancake). Chỉ đọc; hành động dispatch về hội thoại gốc."""
    _name = 'vct.social.thread'
    _description = 'Hội thoại hợp nhất'
    _auto = False
    _order = 'last_message_at desc'

    name = fields.Char('Khách', readonly=True)
    channel = fields.Selection([
        ('zalo', 'Zalo'), ('messenger', 'Messenger'),
    ], string='Kênh', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', readonly=True)
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', readonly=True)
    state = fields.Selection([
        ('bot', 'Bot'), ('human', 'Nhân viên'), ('closed', 'Đóng'),
    ], string='Trạng thái', readonly=True)
    last_message_at = fields.Datetime('Tin gần nhất', readonly=True)
    res_model = fields.Char(readonly=True)
    res_id_ref = fields.Integer(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW vct_social_thread AS (
                SELECT z.id AS id,
                       'zalo'::varchar AS channel,
                       z.partner_id, z.ticket_id, z.state::varchar AS state,
                       z.last_message_at, z.name,
                       'vct.zalo.conversation'::varchar AS res_model, z.id AS res_id_ref
                FROM vct_zalo_conversation z
                UNION ALL
                SELECT (m.id + 1000000) AS id,
                       'messenger'::varchar AS channel,
                       m.partner_id, m.ticket_id, m.state::varchar AS state,
                       m.last_message_at, m.name,
                       'vct.messenger.conversation'::varchar AS res_model, m.id AS res_id_ref
                FROM vct_messenger_conversation m
            )
        """)

    def action_open_source(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Hội thoại'),
            'res_model': self.res_model, 'res_id': self.res_id_ref,
            'view_mode': 'form', 'target': 'current',
        }

    def action_chot_don(self):
        self.ensure_one()
        return self.env['vct.social.order.wizard']._open_for(
            self.partner_id, _('%(kenh)s: %(ten)s', kenh=self.channel, ten=self.name or ''))

    def action_open_ticket(self):
        self.ensure_one()
        if not self.ticket_id:
            raise UserError(_('Hội thoại chưa gắn ticket.'))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id, 'view_mode': 'form',
        }
