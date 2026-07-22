# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket CSKH', index=True, ondelete='set null',
        help='Ticket đã sinh ra việc kỹ thuật viên này.')
