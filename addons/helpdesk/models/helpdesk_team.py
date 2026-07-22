# Written for VCT Platform. Not part of Odoo S.A.

import random

from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _name = 'helpdesk.team'
    _description = 'Helpdesk Team'
    _inherit = ['mail.alias.mixin', 'mail.thread']
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    description = fields.Html(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Working Hours',
        default=lambda self: self.env.company.resource_calendar_id,
        help="Schedule the SLA deadlines are counted along. Without one, they are "
             "counted in plain elapsed time.")
    member_ids = fields.Many2many(
        'res.users', string='Team Members',
        domain=lambda self: [('all_group_ids', 'in', self.env.ref('helpdesk.group_helpdesk_user').ids)])
    assign_method = fields.Selection([
        ('manual', 'Manually'),
        ('random', 'Random'),
        ('balanced', 'Balanced'),
    ], string='Assignment Method', default='manual', required=True,
        help="New tickets are assigned:\n"
             "- Manually: by hand\n"
             "- Random: to a random team member\n"
             "- Balanced: to the team member with the fewest open tickets")
    stage_ids = fields.Many2many(
        'helpdesk.stage', compute='_compute_stage_ids', string='Stages')
    closed_stage_id = fields.Many2one(
        'helpdesk.stage', compute='_compute_closed_stage_id', string='Closing Stage',
        help="Stage a ticket is moved to when its customer closes it from the portal.")
    sla_ids = fields.One2many('helpdesk.sla', 'team_id', string='SLA Policies')
    allow_portal_close = fields.Boolean(
        string='Closable by Customers',
        help="Let customers close their own tickets from the portal.")
    ticket_count = fields.Integer(compute='_compute_ticket_count', string='Open Tickets')

    def _compute_stage_ids(self):
        for team in self:
            team.stage_ids = self.env['helpdesk.stage'].search(
                ['|', ('team_ids', '=', False), ('team_ids', 'in', team.ids)])

    @api.depends('stage_ids')
    def _compute_closed_stage_id(self):
        for team in self:
            team.closed_stage_id = team.stage_ids.filtered('fold')[:1]

    def _compute_ticket_count(self):
        counts = dict(self.env['helpdesk.ticket']._read_group(
            [('team_id', 'in', self.ids), ('stage_id.fold', '=', False)],
            ['team_id'], ['__count']))
        for team in self:
            team.ticket_count = counts.get(team, 0)

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get_id('helpdesk.ticket')
        if self.id:
            values['alias_defaults'] = {'team_id': self.id}
        return values

    def _get_new_user(self, extra_counts=None):
        """Return the user to assign a new ticket to, following the team's
        assignment method (empty recordset when manual or no members).

        :param dict extra_counts: user id -> count of tickets assigned in the
            current batch but not yet in database (for balanced assignment).
        """
        self.ensure_one()
        members = self.member_ids
        if self.assign_method == 'manual' or not members:
            return self.env['res.users']
        if self.assign_method == 'random':
            return members[random.randrange(len(members))]
        # balanced: member with the fewest open tickets
        counts = dict(self.env['helpdesk.ticket']._read_group(
            [('team_id', '=', self.id), ('user_id', 'in', members.ids), ('stage_id.fold', '=', False)],
            ['user_id'], ['__count']))
        extra_counts = extra_counts or {}
        return min(members, key=lambda user: counts.get(user, 0) + extra_counts.get(user.id, 0))

    def action_view_tickets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk.helpdesk_ticket_action_main')
        action['domain'] = [('team_id', '=', self.id)]
        action['context'] = {'default_team_id': self.id}
        return action
