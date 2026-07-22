# Written for VCT Platform. Not part of Odoo S.A.

from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    appointment_type_id = fields.Many2one(
        'appointment.type', string='Loại lịch hẹn', ondelete='set null',
        index='btree_not_null')
