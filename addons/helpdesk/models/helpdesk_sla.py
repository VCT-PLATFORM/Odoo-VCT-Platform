# Written for VCT Platform. Not part of Odoo S.A.

from datetime import timedelta

from odoo import api, fields, models

from .helpdesk_ticket import HELPDESK_PRIORITY


class HelpdeskSla(models.Model):
    _name = 'helpdesk.sla'
    _description = 'Helpdesk SLA Policy'
    _order = 'name'

    name = fields.Char(string='SLA Policy', required=True, translate=True)
    description = fields.Html(translate=True)
    active = fields.Boolean(default=True)
    team_id = fields.Many2one(
        'helpdesk.team', string='Team', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='team_id.company_id', store=True)
    stage_id = fields.Many2one(
        'helpdesk.stage', string='Target Stage', required=True,
        help="The policy is reached once the ticket enters this stage, or any stage after it.")
    priority = fields.Selection(
        HELPDESK_PRIORITY, string='Minimum Priority', default='0', required=True,
        help="Tickets below this priority are not covered by the policy.")
    tag_ids = fields.Many2many(
        'helpdesk.tag', string='Tags',
        help="Cover only the tickets carrying all of these tags. Leave empty to cover every ticket.")
    time = fields.Float(
        string='Within', required=True, default=8.0,
        help="Working hours to reach the target stage, counted from the ticket creation date "
             "along the team's working schedule.")

    _time_positive = models.Constraint(
        'CHECK("time" > 0)',
        'The time to reach an SLA policy must be positive.',
    )

    def _covering(self, ticket):
        """Return the policies of self that cover the given ticket."""
        return self.filtered(lambda sla: (
            ticket.priority >= sla.priority
            and sla.tag_ids <= ticket.tag_ids
        ))


class HelpdeskSlaStatus(models.Model):
    _name = 'helpdesk.sla.status'
    _description = 'Helpdesk SLA Status'
    _order = 'deadline, id'

    ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket', required=True, ondelete='cascade', index=True)
    sla_id = fields.Many2one(
        'helpdesk.sla', string='SLA Policy', required=True, ondelete='cascade')
    sla_stage_id = fields.Many2one(related='sla_id.stage_id', string='Target Stage')
    deadline = fields.Datetime(compute='_compute_deadline', store=True)
    reached_datetime = fields.Datetime(string='Reached On', copy=False)
    status = fields.Selection([
        ('ongoing', 'Ongoing'),
        ('reached', 'Reached'),
        ('failed', 'Failed'),
    ], compute='_compute_status')

    _ticket_sla_uniq = models.Constraint(
        'unique (ticket_id, sla_id)',
        'A ticket can only track a given SLA policy once.',
    )

    @api.depends('ticket_id.create_date', 'sla_id.time', 'ticket_id.team_id.resource_calendar_id')
    def _compute_deadline(self):
        for status in self:
            start = status.ticket_id.create_date or fields.Datetime.now()
            calendar = status.ticket_id.team_id.resource_calendar_id
            deadline = calendar.plan_hours(status.sla_id.time, start, compute_leaves=True) if calendar else False
            # Without a working schedule, or one with no attendance at all, the
            # deadline falls back on plain elapsed time.
            status.deadline = deadline or start + timedelta(hours=status.sla_id.time)

    @api.depends('deadline', 'reached_datetime')
    def _compute_status(self):
        now = fields.Datetime.now()
        for status in self:
            if status.reached_datetime:
                status.status = 'failed' if status.reached_datetime > status.deadline else 'reached'
            else:
                status.status = 'failed' if status.deadline < now else 'ongoing'
