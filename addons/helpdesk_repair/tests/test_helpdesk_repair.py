# Written for VCT Platform. Not part of Odoo S.A.

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHelpdeskRepair(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Khách hàng'})
        cls.ticket = cls.env['helpdesk.ticket'].create({
            'name': 'Máy không chạy',
            'partner_id': cls.partner.id,
        })

    def _repair(self, **values):
        return self.env['repair.order'].create({'partner_id': self.partner.id, **values})

    def test_action_prefills_the_repair_from_the_ticket(self):
        action = self.ticket.action_create_repair()
        self.assertEqual(action['res_model'], 'repair.order')
        self.assertEqual(action['context']['default_ticket_id'], self.ticket.id)
        self.assertEqual(action['context']['default_partner_id'], self.partner.id)

    def test_repairs_link_back_and_are_counted(self):
        self.assertEqual(self.ticket.repair_count, 0)
        repair = self._repair(ticket_id=self.ticket.id)
        self.assertEqual(self.ticket.repair_count, 1)
        self.assertEqual(self.ticket.repair_ids, repair)
        self.assertEqual(repair.ticket_id, self.ticket)

    def test_view_action_opens_the_single_repair_directly(self):
        repair = self._repair(ticket_id=self.ticket.id)
        action = self.ticket.action_view_repairs()
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['res_id'], repair.id)

    def test_view_action_lists_several_repairs(self):
        self._repair(ticket_id=self.ticket.id)
        self._repair(ticket_id=self.ticket.id)
        action = self.ticket.action_view_repairs()
        self.assertEqual(action['view_mode'], 'list,form')
        self.assertEqual(self.ticket.repair_count, 2)

    def test_repairs_of_other_tickets_are_not_counted(self):
        other = self.env['helpdesk.ticket'].create({'name': 'Phiếu khác'})
        self._repair(ticket_id=other.id)
        self.assertEqual(self.ticket.repair_count, 0)
        self.assertEqual(other.repair_count, 1)

    def test_deleting_a_ticket_does_not_delete_its_repairs(self):
        """A repair order is stock/accounting material: it must survive the
        ticket that happened to spawn it."""
        repair = self._repair(ticket_id=self.ticket.id)
        self.ticket.unlink()
        self.assertTrue(repair.exists(), "the repair order must not be cascaded away")
        self.assertFalse(repair.ticket_id)
