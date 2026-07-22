# Written for VCT Platform. Not part of Odoo S.A.

from odoo import api, fields, models
from odoo.tools import email_normalize, parse_contact_from_email

HELPDESK_PRIORITY = [
    ('0', 'Low'),
    ('1', 'Medium'),
    ('2', 'High'),
    ('3', 'Urgent'),
]


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _description = 'Helpdesk Ticket'
    _inherit = ['portal.mixin', 'mail.thread.cc', 'mail.activity.mixin', 'rating.mixin']
    _order = 'priority desc, id desc'
    _primary_email = 'partner_email'
    _mail_post_access = 'read'
    _mail_thread_customer = True

    @api.model
    def _default_team_id(self):
        return self.env['helpdesk.team'].search([], limit=1)

    name = fields.Char(string='Subject', required=True, tracking=True)
    description = fields.Html()
    active = fields.Boolean(default=True)
    team_id = fields.Many2one(
        'helpdesk.team', string='Team', required=True, index=True, tracking=True,
        default=_default_team_id)
    company_id = fields.Many2one(related='team_id.company_id', store=True)
    stage_id = fields.Many2one(
        'helpdesk.stage', string='Stage', index=True, tracking=True, copy=False,
        group_expand='_read_group_stage_ids',
        compute='_compute_stage_id', store=True, readonly=False,
        domain="['|', ('team_ids', '=', False), ('team_ids', 'in', team_id)]")
    user_id = fields.Many2one(
        'res.users', string='Assigned to', index=True, tracking=True,
        domain=lambda self: [('all_group_ids', 'in', self.env.ref('helpdesk.group_helpdesk_user').ids)])
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    partner_name = fields.Char(
        string='Customer Name', compute='_compute_partner_info', store=True, readonly=False)
    partner_email = fields.Char(
        string='Customer Email', compute='_compute_partner_info', store=True, readonly=False)
    priority = fields.Selection(
        HELPDESK_PRIORITY, string='Priority', default='0', index=True, tracking=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    color = fields.Integer(string='Color Index')
    assign_date = fields.Datetime(string='First Assignment Date', copy=False)
    close_date = fields.Datetime(string='Close Date', copy=False)

    sla_status_ids = fields.One2many(
        'helpdesk.sla.status', 'ticket_id', string='SLA Status', copy=False)
    sla_deadline = fields.Datetime(
        string='SLA Deadline', compute='_compute_sla_deadline', compute_sudo=True, store=True,
        help="Deadline of the next SLA policy left to reach.")
    sla_fail = fields.Boolean(
        string='Failed SLA Policy', compute='_compute_sla_deadline', compute_sudo=True, store=True,
        help="At least one SLA policy was reached after its deadline.")

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order=stages._order)

    @api.depends('team_id')
    def _compute_stage_id(self):
        for ticket in self:
            if not ticket.stage_id or (ticket.team_id.stage_ids
                    and ticket.stage_id not in ticket.team_id.stage_ids):
                ticket.stage_id = ticket.team_id.stage_ids[:1]

    @api.depends('partner_id')
    def _compute_partner_info(self):
        for ticket in self:
            if ticket.partner_id:
                ticket.partner_name = ticket.partner_id.name
                ticket.partner_email = ticket.partner_id.email

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_deadline(self):
        now = fields.Datetime.now()
        for ticket in self:
            ongoing = ticket.sla_status_ids.filtered(lambda s: not s.reached_datetime)
            ticket.sla_deadline = min(ongoing.mapped('deadline'), default=False)
            # a status being unlinked has no deadline yet: guard both sides
            ticket.sla_fail = any(
                status.deadline and status.reached_datetime > status.deadline
                for status in ticket.sla_status_ids - ongoing
            ) or any(status.deadline and status.deadline < now for status in ongoing)

    @api.model
    def _cron_flag_sla_failures(self, date=None):
        """sla_fail is stored, but breaching a deadline is something *time* does,
        not something a write does: a ticket left untouched past its deadline
        would stay flagged green forever without this."""
        now = date or fields.Datetime.now()
        breached = self.search([
            ('sla_fail', '=', False),
            ('sla_deadline', '!=', False),
            ('sla_deadline', '<', now),
        ])
        breached.invalidate_recordset(['sla_fail'])
        breached.modified(['sla_status_ids'])
        breached._compute_sla_deadline()
        return breached

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = f'/my/tickets/{ticket.id}'

    @api.model
    def _clean_partner_email(self, vals):
        """Being the primary email field, partner_email gets the raw
        "Name <email>" from address stamped into it by the mail gateway. Keep it
        a plain address whatever writes it."""
        if vals.get('partner_email'):
            vals['partner_email'] = email_normalize(vals['partner_email']) or vals['partner_email']

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        batch_counts = {}
        for vals in vals_list:
            self._clean_partner_email(vals)
            team = self.env['helpdesk.team'].browse(vals.get('team_id')) \
                if vals.get('team_id') else self._default_team_id()
            if team and not vals.get('user_id'):
                user = team._get_new_user(extra_counts=batch_counts)
                if user:
                    vals['user_id'] = user.id
                    batch_counts[user.id] = batch_counts.get(user.id, 0) + 1
            if vals.get('user_id'):
                vals['assign_date'] = now
        tickets = super().create(vals_list)
        tickets._sla_apply()
        tickets._sla_reach()
        return tickets

    def write(self, vals):
        self._clean_partner_email(vals)
        if vals.get('user_id'):
            for ticket in self.filtered(lambda t: not t.assign_date):
                ticket.assign_date = fields.Datetime.now()
        res = super().write(vals)
        if 'stage_id' in vals:
            closing = self.filtered(lambda t: t.stage_id.fold)
            closing.filtered(lambda t: not t.close_date).close_date = fields.Datetime.now()
            (self - closing).close_date = False
            self._send_ticket_rating_mail()
        if {'team_id', 'priority', 'tag_ids'} & vals.keys():
            self._sla_apply()
        if {'team_id', 'priority', 'tag_ids', 'stage_id'} & vals.keys():
            self._sla_reach()
        return res

    # ---------------------------------------------------
    # SLA business
    # ---------------------------------------------------

    def _sla_apply(self):
        """Track the SLA policies covering the tickets, and stop tracking the
        ones that no longer cover them. Reached policies are always kept."""
        status_values = []
        for ticket in self:
            covered = ticket.team_id.sla_ids._covering(ticket)
            obsolete = ticket.sla_status_ids.filtered(
                lambda status: not status.reached_datetime and status.sla_id not in covered)
            kept = ticket.sla_status_ids - obsolete
            obsolete.unlink()
            status_values += [
                {'ticket_id': ticket.id, 'sla_id': sla.id}
                for sla in covered - kept.sla_id
            ]
        self.env['helpdesk.sla.status'].create(status_values)

    def _sla_reach(self):
        """Stamp the tracked policies whose target stage has been passed."""
        now = fields.Datetime.now()
        for ticket in self:
            ticket.sla_status_ids.filtered(
                lambda status: not status.reached_datetime
                and status.sla_id.stage_id.sequence <= ticket.stage_id.sequence
            ).reached_datetime = now

    # ---------------------------------------------------
    # Rating business
    # ---------------------------------------------------

    def _send_ticket_rating_mail(self, force_send=False):
        for ticket in self:
            template = ticket.stage_id.rating_template_id
            partner = ticket._rating_get_partner()
            if template and partner and partner != self.env.user.partner_id:
                ticket.rating_send_request(template, lang=partner.lang, force_send=force_send)

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _track_template(self, changes):
        res = super()._track_template(changes)
        ticket = self[0]
        if 'stage_id' in changes and ticket.stage_id.template_id:
            res['stage_id'] = (ticket.stage_id.template_id, {
                'auto_delete_keep_log': False,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light',
            })
        return res

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a ticket from an incoming email sent to a team alias."""
        custom_values = dict(custom_values or {})
        custom_values.setdefault('name', msg_dict.get('subject') or self.env._('New Ticket'))
        name, email = parse_contact_from_email(msg_dict.get('email_from') or '')
        if email and 'partner_id' not in custom_values:
            partner = self.env['res.partner'].search([('email_normalized', '=', email)], limit=1)
            if partner:
                custom_values['partner_id'] = partner.id
            else:
                custom_values.setdefault('partner_name', name or email)
        return super().message_new(msg_dict, custom_values=custom_values)
