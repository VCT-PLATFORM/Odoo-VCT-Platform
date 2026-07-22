# Written for VCT Platform. Not part of Odoo S.A.
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPrivacy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Priv = cls.env['vct.cs.privacy.config']
        cls.config = cls.Priv._get_active()
        cls.team = cls.env['helpdesk.team'].create({'name': 'Priv team'})

    def _enable(self, **flags):
        vals = {'mask_enabled': True, 'mask_cards': False, 'mask_id': False, 'mask_phone': False}
        vals.update(flags)
        self.config.write(vals)

    # ---- masking ----
    def test_disabled_passthrough(self):
        self.config.write({'mask_enabled': False})
        self.assertEqual(self.Priv._mask_text('thẻ 1234 5678 9012 3456'), 'thẻ 1234 5678 9012 3456')

    def test_mask_card(self):
        self._enable(mask_cards=True)
        out = self.Priv._mask_text('Số thẻ 1234 5678 9012 3456 nhé')
        self.assertIn('3456', out)
        self.assertNotIn('1234 5678', out)
        self.assertIn('*', out)

    def test_mask_phone_when_enabled(self):
        self._enable(mask_phone=True)
        out = self.Priv._mask_text('gọi 0912345678')
        self.assertIn('5678', out)
        self.assertNotIn('091234', out)

    def test_mask_id_when_enabled(self):
        self._enable(mask_id=True)
        out = self.Priv._mask_text('CCCD 079201234567')
        self.assertIn('4567', out)
        self.assertNotIn('079201', out)

    def test_phone_not_masked_by_default(self):
        self._enable(mask_cards=True)   # phone off
        out = self.Priv._mask_text('gọi 0912345678')
        self.assertIn('0912345678', out, 'không bật che SĐT thì giữ nguyên')

    # ---- áp vào ticket ----
    def test_message_post_masks_body(self):
        self._enable(mask_cards=True)
        t = self.env['helpdesk.ticket'].create({'name': 'x', 'team_id': self.team.id})
        msg = t.message_post(body='Thẻ 4111 1111 1111 1111', message_type='comment',
                             subtype_xmlid='mail.mt_comment')
        self.assertNotIn('4111 1111 1111 1111', msg.body or '')
        self.assertIn('1111', msg.body or '')

    # ---- retention ----
    def test_retention_archives_old_closed(self):
        self.config.write({'retention_months': 1})
        fold_stage = self.env['helpdesk.stage'].create(
            {'name': 'Đóng test', 'fold': True, 'team_ids': [(4, self.team.id)]})
        t = self.env['helpdesk.ticket'].create(
            {'name': 'cũ', 'team_id': self.team.id, 'stage_id': fold_stage.id})
        old = fields.Datetime.to_string(fields.Datetime.now() - relativedelta(months=2))
        self.env.cr.execute("UPDATE helpdesk_ticket SET write_date=%s WHERE id=%s", (old, t.id))
        t.invalidate_recordset(['write_date'])
        self.Priv._cron_apply_retention()
        self.assertFalse(t.active, 'ticket đóng quá hạn phải được lưu trữ (archive)')
