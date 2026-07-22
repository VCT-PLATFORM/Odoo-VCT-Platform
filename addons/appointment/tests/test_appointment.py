# Written for VCT Platform. Not part of Odoo S.A.

from datetime import datetime

import pytz
from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

TZ = 'Asia/Ho_Chi_Minh'  # UTC+7, no DST


@tagged('post_install', '-at_install')
class TestAppointment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Test 8-12 13-17',
            'tz': TZ,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': f'{day}-{label}', 'dayofweek': str(day),
                        'hour_from': hour_from, 'hour_to': hour_to,
                        'day_period': period})
                for day in range(5)
                for label, hour_from, hour_to, period in [
                    ('am', 8.0, 12.0, 'morning'), ('pm', 13.0, 17.0, 'afternoon')]
            ],
        })
        cls.staff = cls.env['res.users'].create({
            'name': 'Nhân viên tiếp', 'login': 'staff_appt_test', 'tz': TZ,
        })
        cls.appointment_type = cls.env['appointment.type'].create({
            'name': 'Tư vấn',
            'duration': 1.0,
            'staff_user_ids': [(6, 0, cls.staff.ids)],
            'resource_calendar_id': cls.calendar.id,
            'tz': TZ,
            'min_hours_before': 0.0,
            'max_days_ahead': 1,
        })
        cls.customer = cls.env['res.partner'].create({
            'name': 'Khách', 'email': 'khach_appt_test@example.com',
        })

    def _local(self, slot_utc):
        return pytz.utc.localize(slot_utc).astimezone(pytz.timezone(TZ))

    # 2026-07-20 is a Monday. 00:00 UTC = 07:00 local, before the 08:00 shift.
    @freeze_time('2026-07-20 00:00:00')
    def test_slots_land_only_inside_working_hours(self):
        slots = self.appointment_type._get_available_slots(self.staff)
        self.assertTrue(slots, 'giờ làm việc Thứ Hai phải sinh ra khung giờ')
        for slot in slots:
            local = self._local(slot)
            self.assertEqual(local.weekday(), 0, 'chỉ Thứ Hai nằm trong cửa sổ 1 ngày')
            in_morning = 8 <= local.hour < 12
            in_afternoon = 13 <= local.hour < 17
            self.assertTrue(
                in_morning or in_afternoon,
                f'{local:%H:%M} nằm ngoài ca 08-12 / 13-17')
        # 4h sáng + 4h chiều, mỗi khung 1h
        self.assertEqual(len(slots), 8)

    @freeze_time('2026-07-20 00:00:00')
    def test_booking_removes_that_slot(self):
        before = self.appointment_type._get_available_slots(self.staff)
        target = before[0]
        event = self.appointment_type._create_appointment(
            target, self.customer, self.staff)
        self.assertTrue(event, 'phải đặt được khung giờ đang trống')

        after = self.appointment_type._get_available_slots(self.staff)
        self.assertNotIn(target, after, 'khung giờ đã đặt phải biến mất')
        self.assertEqual(len(after), len(before) - 1, 'chỉ mất đúng 1 khung giờ')
        self.assertEqual(event.appointment_type_id, self.appointment_type)
        self.assertIn(self.customer, event.partner_ids)
        self.assertIn(self.staff.partner_id, event.partner_ids)

    @freeze_time('2026-07-20 00:00:00')
    def test_second_booking_of_same_slot_is_refused(self):
        """Two customers can render the page and submit the same slot; the
        second must be turned away, not silently double-booked."""
        target = self.appointment_type._get_available_slots(self.staff)[0]
        self.appointment_type._create_appointment(target, self.customer, self.staff)

        other = self.env['res.partner'].create(
            {'name': 'Khách 2', 'email': 'khach2_appt_test@example.com'})
        self.assertFalse(
            self.appointment_type._first_available_staff(target),
            'không còn ai rảnh vào khung giờ đó')
        self.assertFalse(
            self.appointment_type._create_appointment(target, other),
            'lịch hẹn thứ hai vào cùng khung giờ phải bị từ chối')

    @freeze_time('2026-07-20 00:00:00')
    def test_min_hours_before_hides_imminent_slots(self):
        self.appointment_type.min_hours_before = 4.0  # now 07:00 local -> cutoff 11:00
        for slot in self.appointment_type._get_available_slots(self.staff):
            self.assertGreaterEqual(
                slot, fields.Datetime.now(),
                'không được chào khung giờ trong quá khứ')
            self.assertGreaterEqual(
                self._local(slot).hour, 11,
                'khung giờ sớm hơn hạn đặt trước phải bị loại')

    def test_duration_longer_than_shift_is_refused_at_config_time(self):
        """A 9h slot against a 4h shift silently yields an empty booking page.
        Fail loudly when it is configured instead."""
        with self.assertRaises(ValidationError):
            self.appointment_type.duration = 9.0

    @freeze_time('2026-07-18 00:00:00')  # Saturday
    def test_no_slots_on_closed_days(self):
        self.appointment_type.max_days_ahead = 1
        self.assertFalse(
            self.appointment_type._get_available_slots(self.staff),
            'cuối tuần không nằm trong giờ làm việc nên không có khung giờ')

    @freeze_time('2026-07-20 00:00:00')
    def test_time_off_removes_slots(self):
        """resource.calendar already subtracts leaves; prove we inherit that
        rather than re-implementing it."""
        before = len(self.appointment_type._get_available_slots(self.staff))
        self.env['resource.calendar.leaves'].create({
            'name': 'Nghỉ lễ',
            'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 7, 20, 1, 0),   # 08:00 local
            'date_to': datetime(2026, 7, 20, 5, 0),     # 12:00 local
        })
        after = len(self.appointment_type._get_available_slots(self.staff))
        self.assertEqual(after, before - 4, 'cả ca sáng phải biến mất khi nghỉ')
