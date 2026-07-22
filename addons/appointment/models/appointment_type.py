# Written for VCT Platform. Not part of Odoo S.A.

from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _description = 'Loại lịch hẹn'
    _order = 'sequence, id'

    name = fields.Char(string='Tên', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    duration = fields.Float(
        string='Thời lượng (giờ)', required=True, default=1.0,
        help='Mỗi khung giờ dài bấy nhiêu. 0,5 = 30 phút.')
    staff_user_ids = fields.Many2many(
        'res.users', string='Nhân sự tiếp nhận', required=True,
        domain=[('share', '=', False)])
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Giờ làm việc',
        default=lambda self: self.env.company.resource_calendar_id,
        help='Khung giờ chỉ sinh trong giờ làm việc này, đã trừ ngày nghỉ.')
    company_id = fields.Many2one(
        'res.company', string='Công ty', default=lambda self: self.env.company)
    tz = fields.Selection(
        lambda self: [(t, t) for t in pytz.all_timezones], string='Múi giờ',
        default=lambda self: self.env.user.tz or 'Asia/Ho_Chi_Minh', required=True)
    location = fields.Char(string='Địa điểm', translate=True)
    description = fields.Html(string='Mô tả', translate=True, sanitize=True)
    min_hours_before = fields.Float(
        string='Đặt trước tối thiểu (giờ)', default=1.0,
        help='Không cho đặt khung giờ gần hơn khoảng này kể từ bây giờ.')
    max_days_ahead = fields.Integer(
        string='Mở lịch trước (ngày)', default=30, required=True)
    website_published = fields.Boolean(string='Đăng lên website', default=True)
    appointment_count = fields.Integer(
        string='Số lịch hẹn', compute='_compute_appointment_count')

    _duration_positive = models.Constraint(
        'CHECK(duration > 0)', 'Thời lượng phải lớn hơn 0.')
    _max_days_ahead_positive = models.Constraint(
        'CHECK(max_days_ahead > 0)', 'Số ngày mở lịch phải lớn hơn 0.')

    def _compute_appointment_count(self):
        counts = dict(self.env['calendar.event']._read_group(
            [('appointment_type_id', 'in', self.ids)],
            groupby=['appointment_type_id'], aggregates=['__count'],
        ))
        for appointment_type in self:
            appointment_type.appointment_count = counts.get(appointment_type, 0)

    @api.constrains('duration', 'resource_calendar_id')
    def _check_duration_fits_workday(self):
        """A 9-hour slot against an 8-hour workday yields an empty booking page
        with no explanation. Fail at configuration time instead."""
        for appointment_type in self:
            calendar = appointment_type.resource_calendar_id
            if not calendar or not calendar.attendance_ids:
                continue
            longest = max(
                (a.hour_to - a.hour_from for a in calendar.attendance_ids), default=0)
            if appointment_type.duration > longest:
                raise ValidationError(self.env._(
                    'Thời lượng %(duration)s giờ dài hơn ca làm việc dài nhất '
                    '(%(longest)s giờ) của lịch "%(calendar)s", nên sẽ không sinh '
                    'ra khung giờ nào.',
                    duration=appointment_type.duration, longest=round(longest, 2),
                    calendar=calendar.display_name))

    def _busy_intervals(self, staff_user, start, stop):
        """UTC (start, stop) pairs where this staff member already has an event."""
        events = self.env['calendar.event'].sudo().search([
            ('partner_ids', 'in', staff_user.partner_id.ids),
            ('start', '<', stop),
            ('stop', '>', start),
            ('show_as', '=', 'busy'),
        ])
        return [(e.start, e.stop) for e in events]

    def _get_available_slots(self, staff_user):
        """Bookable UTC start datetimes for one staff member.

        Working hours come from resource.calendar so time off is already
        subtracted; we only remove slots the person is booked for.
        """
        self.ensure_one()
        if staff_user not in self.staff_user_ids:
            return []
        calendar = self.resource_calendar_id or self.env.company.resource_calendar_id
        if not calendar:
            return []

        now = fields.Datetime.now()
        start = now + timedelta(hours=self.min_hours_before)
        stop = now + timedelta(days=self.max_days_ahead)
        tz = pytz.timezone(self.tz)
        intervals = calendar._work_intervals_batch(
            pytz.utc.localize(start), pytz.utc.localize(stop), tz=tz)[False]

        busy = self._busy_intervals(staff_user, start, stop)
        duration = timedelta(hours=self.duration)
        slots = []
        for interval_start, interval_stop, _meta in intervals:
            cursor = interval_start
            while cursor + duration <= interval_stop:
                slot_start = cursor.astimezone(pytz.utc).replace(tzinfo=None)
                slot_stop = slot_start + duration
                # a slot is free only if it overlaps nothing already booked
                if not any(b_start < slot_stop and b_stop > slot_start
                           for b_start, b_stop in busy):
                    slots.append(slot_start)
                cursor += duration
        return slots

    def _first_available_staff(self, slot_start):
        """Whoever is free at that moment. Guards the race between rendering the
        page and submitting it: the slot may have been taken meanwhile."""
        self.ensure_one()
        for staff_user in self.staff_user_ids:
            if slot_start in self._get_available_slots(staff_user):
                return staff_user
        return self.env['res.users']

    def _create_appointment(self, slot_start, partner, staff_user=None):
        """Book the slot. Returns an empty recordset if it is no longer free."""
        self.ensure_one()
        staff_user = staff_user or self._first_available_staff(slot_start)
        if not staff_user:
            return self.env['calendar.event']
        return self.env['calendar.event'].sudo().create({
            'name': self.env._('%(type)s - %(partner)s',
                               type=self.name, partner=partner.name),
            'start': slot_start,
            'stop': slot_start + timedelta(hours=self.duration),
            'duration': self.duration,
            'user_id': staff_user.id,
            'partner_ids': [(6, 0, (staff_user.partner_id | partner).ids)],
            'location': self.location,
            'appointment_type_id': self.id,
        })

    def action_view_appointments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Lịch hẹn'),
            'res_model': 'calendar.event',
            'view_mode': 'calendar,list,form',
            'domain': [('appointment_type_id', '=', self.id)],
            'context': {'default_appointment_type_id': self.id},
        }
