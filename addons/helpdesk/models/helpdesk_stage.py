# Written for VCT Platform. Not part of Odoo S.A.

from odoo import fields, models


class HelpdeskStage(models.Model):
    _name = 'helpdesk.stage'
    _description = 'Helpdesk Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(
        string='Folded in Kanban',
        help="Tickets in a folded stage are considered as closed.")
    team_ids = fields.Many2many(
        'helpdesk.team', string='Teams',
        help="Specific teams using this stage. Empty means shared by all teams.")
    template_id = fields.Many2one(
        'mail.template', string='Email Template',
        domain=[('model', '=', 'helpdesk.ticket')],
        help="Automatically sent to the customer when the ticket reaches this stage.")
    rating_template_id = fields.Many2one(
        'mail.template', string='Rating Email Template',
        domain=[('model', '=', 'helpdesk.ticket')],
        help="If set, a satisfaction survey is automatically sent to the customer "
             "when the ticket reaches this stage.")


class HelpdeskTag(models.Model):
    _name = 'helpdesk.tag'
    _description = 'Helpdesk Tag'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(string='Color Index', default=10)

    _name_uniq = models.Constraint(
        'unique (name)',
        'A tag with the same name already exists.',
    )
