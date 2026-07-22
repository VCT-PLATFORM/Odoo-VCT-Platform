# Written for VCT Platform. Not part of Odoo S.A.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApprovals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        g = cls.env.ref('base.group_user').id
        cls.Req = cls.env['approval.request']

        def user(login):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'group_ids': [(6, 0, [g])]})
        cls.u1 = user('appr1')
        cls.u2 = user('appr2')
        cls.owner = user('reqowner')
        cls.cat2 = cls.env['approval.category'].create({
            'name': 'Mua sắm test', 'approval_minimum': 2, 'user_ids': [(6, 0, [cls.u1.id, cls.u2.id])]})

    def _req(self, category=None):
        return self.Req.create({
            'name': 'Mua laptop', 'category_id': (category or self.cat2).id,
            'request_owner_id': self.owner.id})

    def test_confirm_loads_approvers_and_pends(self):
        req = self._req()
        req.action_confirm()
        self.assertEqual(req.state, 'pending')
        self.assertEqual(len(req.approver_ids), 2)
        self.assertTrue(all(a.status == 'pending' for a in req.approver_ids))
        # hoạt động nhắc được tạo cho người duyệt
        self.assertTrue(req.activity_ids)

    def test_reaches_minimum_then_approved(self):
        req = self._req()
        req.action_confirm()
        req.with_user(self.u1).action_approve()
        self.assertEqual(req.approved_count, 1)
        self.assertEqual(req.state, 'pending', 'chưa đủ ngưỡng 2 → vẫn chờ')
        req.with_user(self.u2).action_approve()
        self.assertEqual(req.state, 'approved', 'đủ 2 duyệt → thông qua')

    def test_refuse_sets_refused(self):
        req = self._req()
        req.action_confirm()
        req.with_user(self.u1).action_refuse()
        self.assertEqual(req.state, 'refused')

    def test_non_approver_cannot_approve(self):
        req = self._req()
        req.action_confirm()
        with self.assertRaises(UserError):
            req.with_user(self.owner).action_approve()

    def test_can_approve_flag_per_user(self):
        req = self._req()
        req.action_confirm()
        self.assertTrue(req.with_user(self.u1).can_approve)
        self.assertFalse(req.with_user(self.owner).can_approve)

    def test_confirm_requires_enough_approvers(self):
        cat3 = self.env['approval.category'].create({
            'name': 'Cần 3 duyệt', 'approval_minimum': 3, 'user_ids': [(6, 0, [self.u1.id, self.u2.id])]})
        req = self._req(category=cat3)
        with self.assertRaises(UserError):
            req.action_confirm()

    def test_withdraw_reopens(self):
        req = self._req()
        req.action_confirm()
        req.with_user(self.u1).action_approve()
        req.with_user(self.u2).action_approve()
        self.assertEqual(req.state, 'approved')
        req.with_user(self.u2).action_withdraw()
        self.assertEqual(req.state, 'pending', 'rút duyệt → mở lại chờ')
