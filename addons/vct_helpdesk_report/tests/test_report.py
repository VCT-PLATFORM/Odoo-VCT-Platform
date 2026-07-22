# Written for VCT Platform. Not part of Odoo S.A.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReport(TransactionCase):

    def test_action_and_views_exist(self):
        action = self.env.ref('vct_helpdesk_report.action_helpdesk_cs_analysis')
        self.assertEqual(action.res_model, 'helpdesk.ticket')
        self.assertIn('pivot', action.view_mode)
        # view refs hợp lệ (arch pivot/graph đã được Odoo kiểm khi cài)
        self.assertTrue(self.env.ref('vct_helpdesk_report.helpdesk_ticket_view_pivot_cs'))
        self.assertTrue(self.env.ref('vct_helpdesk_report.helpdesk_ticket_view_graph_cs'))

    def test_pivot_read_group_by_tier_runs(self):
        # chứng minh chiều CS×ERP (hạng KH) truy vấn được để pivot dùng
        self.env['helpdesk.ticket']._read_group(
            [], groupby=['cs_tier_id'], aggregates=['__count'])
