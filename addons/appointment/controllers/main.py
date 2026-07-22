# Written for VCT Platform. Not part of Odoo S.A.

from collections import defaultdict

import pytz

from odoo import fields, http
from odoo.http import request


class AppointmentController(http.Controller):

    def _published_types(self):
        return request.env['appointment.type'].sudo().search(
            [('website_published', '=', True)])

    @http.route('/dat-lich', type='http', auth='public', website=True, sitemap=True)
    def appointment_index(self, **kwargs):
        types = self._published_types()
        if len(types) == 1:
            return request.redirect(f'/dat-lich/{types.id}')
        return request.render('appointment.appointment_index', {
            'appointment_types': types,
        })

    @http.route('/dat-lich/<model("appointment.type"):appointment_type>',
                type='http', auth='public', website=True, sitemap=True)
    def appointment_slots(self, appointment_type, **kwargs):
        appointment_type = appointment_type.sudo()
        if not appointment_type.website_published:
            return request.not_found()

        tz = pytz.timezone(appointment_type.tz)
        # merge every staff member's free slots: the customer picks a time, not
        # a person, and _create_appointment assigns whoever is still free
        slots = set()
        for staff_user in appointment_type.staff_user_ids:
            slots.update(appointment_type._get_available_slots(staff_user))

        by_day = defaultdict(list)
        for slot in sorted(slots):
            local = pytz.utc.localize(slot).astimezone(tz)
            by_day[local.date()].append((slot, local))

        return request.render('appointment.appointment_slots', {
            'appointment_type': appointment_type,
            'slots_by_day': sorted(by_day.items()),
            'error': kwargs.get('error'),
        })

    @http.route('/dat-lich/<model("appointment.type"):appointment_type>/confirm',
                type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def appointment_confirm(self, appointment_type, slot='', name='', email='',
                            phone='', **kwargs):
        appointment_type = appointment_type.sudo()
        if not appointment_type.website_published:
            return request.not_found()

        name, email = name.strip(), email.strip()
        if not name or not email:
            return request.redirect(
                f'/dat-lich/{appointment_type.id}?error=missing')
        try:
            slot_start = fields.Datetime.from_string(slot)
        except (ValueError, TypeError):
            slot_start = None
        if not slot_start:
            return request.redirect(f'/dat-lich/{appointment_type.id}?error=slot')

        # re-check availability here, not just when rendering: two customers can
        # load the same page and submit the same slot
        staff_user = appointment_type._first_available_staff(slot_start)
        if not staff_user:
            return request.redirect(f'/dat-lich/{appointment_type.id}?error=taken')

        partner = request.env['res.partner'].sudo().search(
            [('email', '=ilike', email)], limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': name, 'email': email, 'phone': phone,
            })
        event = appointment_type._create_appointment(slot_start, partner, staff_user)
        if not event:
            return request.redirect(f'/dat-lich/{appointment_type.id}?error=taken')
        return request.render('appointment.appointment_booked', {
            'appointment_type': appointment_type,
            'event': event,
            'partner': partner,
            'local_start': pytz.utc.localize(event.start).astimezone(
                pytz.timezone(appointment_type.tz)),
        })
