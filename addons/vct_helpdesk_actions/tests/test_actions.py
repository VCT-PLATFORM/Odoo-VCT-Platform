# Written for VCT Platform. Not part of Odoo S.A.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestActions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env['helpdesk.team'].create({'name': 'Act team'})
        cls.partner = cls.env['res.partner'].create({'name': 'KH Act'})
        cls.fsm_project = cls.env['project.project'].search([('is_fsm', '=', True)], limit=1)

    def _ticket(self, **kw):
        vals = {'name': 'Máy hỏng', 'team_id': self.team.id, 'partner_id': self.partner.id}
        vals.update(kw)
        return self.env['helpdesk.ticket'].create(vals)

    def test_create_fsm_action_prefills(self):
        t = self._ticket()
        action = t.action_create_fsm_task()
        ctx = action['context']
        self.assertEqual(action['res_model'], 'project.task')
        self.assertEqual(ctx['default_partner_id'], self.partner.id)
        self.assertEqual(ctx['default_helpdesk_ticket_id'], t.id)
        self.assertTrue(ctx['default_project_id'], 'phải trỏ dự án FSM')

    def test_fsm_task_backlink_and_count(self):
        t = self._ticket()
        task = self.env['project.task'].create({
            'name': 'KTV đến nhà', 'project_id': self.fsm_project.id,
            'partner_id': self.partner.id, 'helpdesk_ticket_id': t.id})
        self.assertEqual(t.fsm_task_count, 1)
        self.assertIn(task, t.fsm_task_ids)

    def test_create_refund_prefills(self):
        t = self._ticket()
        action = t.action_create_refund()
        ctx = action['context']
        self.assertEqual(action['res_model'], 'account.move')
        self.assertEqual(ctx['default_move_type'], 'out_refund')
        self.assertEqual(ctx['default_partner_id'], self.partner.id)

    def test_refund_requires_partner(self):
        t = self._ticket(partner_id=False)
        with self.assertRaises(UserError):
            t.action_create_refund()
