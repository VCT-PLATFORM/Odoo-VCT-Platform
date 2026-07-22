# Written for VCT Platform. Not part of Odoo S.A.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVctHelpdesk(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env['helpdesk.ticket']
        cls.tag_vip = cls.env['helpdesk.tag'].create({'name': 'SLA-VIP'})
        cls.tier_vip = cls.env['vct.cs.tier'].create({
            'name': 'VIP test', 'ticket_priority': '3', 'sla_tag_id': cls.tag_vip.id})
        cls.tier_low = cls.env['vct.cs.tier'].create({
            'name': 'Thấp test', 'ticket_priority': '1'})
        cls.company = cls.env['res.partner'].create({
            'name': 'Công ty VIP', 'is_company': True, 'cs_tier_id': cls.tier_vip.id})
        cls.contact = cls.env['res.partner'].create({
            'name': 'Liên hệ con', 'parent_id': cls.company.id})
        cls.team = cls.env['helpdesk.team'].create({'name': 'Đội hỗ trợ test'})

    def _ticket(self, **kw):
        vals = {'name': 'Ticket thử', 'team_id': self.team.id, 'partner_id': self.company.id}
        vals.update(kw)
        return self.Ticket.create(vals)

    # ---- hạng KH → ưu tiên + thẻ SLA ----
    def test_tier_boosts_priority_and_tags_on_create(self):
        t = self._ticket()
        self.assertEqual(t.priority, '3', 'KH VIP phải nâng ưu tiên lên Khẩn')
        self.assertIn(self.tag_vip, t.tag_ids, 'phải gắn thẻ SLA của hạng')

    def test_tier_does_not_downgrade_manual_priority(self):
        low = self.env['res.partner'].create({
            'name': 'KH thường', 'is_company': True, 'cs_tier_id': self.tier_low.id})
        t = self._ticket(partner_id=low.id, priority='2')
        self.assertEqual(t.priority, '2', 'không được hạ ưu tiên đặt tay xuống theo hạng')

    def test_no_tier_no_change(self):
        plain = self.env['res.partner'].create({'name': 'KH không hạng', 'is_company': True})
        t = self._ticket(partner_id=plain.id)
        self.assertFalse(t.cs_tier_id, 'KH không hạng thì ticket không có hạng')
        self.assertNotIn(self.tag_vip, t.tag_ids, 'không hạng → không gắn thẻ SLA hạng')

    # ---- 360° ----
    def test_commercial_partner_rolls_up_to_company(self):
        t = self._ticket(partner_id=self.contact.id)
        self.assertEqual(t.commercial_partner_id, self.company)
        self.assertEqual(t.cs_tier_id, self.tier_vip, 'hạng lấy theo KH cấp công ty')

    def test_partner_360_aggregates(self):
        o1 = self.env['sale.order'].create({'partner_id': self.company.id})
        o2 = self.env['sale.order'].create({'partner_id': self.contact.id})
        t = self._ticket()
        # thêm 1 ticket khác cùng KH để đếm > 0
        self._ticket()
        self.assertEqual(t.partner_sale_count, 2, 'đếm đơn của cả công ty + liên hệ con')
        self.assertIn(t.partner_last_order_id, (o1 | o2))
        self.assertGreaterEqual(t.partner_ticket_count, 1, 'phải có ticket khác của KH')
        self.assertEqual(t.partner_due_amount, self.company.credit)

    def test_parent_child(self):
        parent = self._ticket(name='Cha')
        child = self._ticket(name='Con', parent_id=parent.id)
        self.assertEqual(child.parent_id, parent)
        self.assertEqual(parent.child_count, 1)
        self.assertIn(child, parent.child_ids)
