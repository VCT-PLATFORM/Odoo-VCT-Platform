# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.addons.vct_helpdesk_ai.models.vct_cs_ai_config import ESCALATE


@tagged('post_install', '-at_install')
class TestCsAi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.acc_cls = type(cls.env['vct.zalo.account'])
        cls.config = cls.env['vct.cs.ai.config']._get_active() or cls.env['vct.cs.ai.config'].create(
            {'name': 'test'})
        cls.config.write({'zalo_autoreply': True, 'include_partner_context': True})
        cls.team = cls.env['helpdesk.team'].create({'name': 'AI team'})
        cls.account = cls.env['vct.zalo.account'].create({
            'name': 'OA AI', 'oa_id': 'OAAI', 'app_id': 'a',
            'default_team_id': cls.team.id, 'access_token': 'T'})
        cls.company = cls.env['res.partner'].create({'name': 'Cty A', 'is_company': True})

    # ---- _answer ----
    def test_answer_returns_text_when_confident(self):
        with patch.object(self.bot_cls, '_run_agent', return_value='Đơn của anh đang giao ạ.') as m:
            answer, esc = self.config._answer(self.company, 'đơn hàng của tôi đâu rồi')
        self.assertFalse(esc)
        self.assertIn('đang giao', answer)
        self.assertEqual(m.call_args.kwargs.get('use_tools'), False,
                         'KHÔNG đưa tool ERP cho model hướng khách')

    def test_escalate_on_sentinel(self):
        with patch.object(self.bot_cls, '_run_agent', return_value='abc ' + ESCALATE):
            answer, esc = self.config._answer(self.company, 'câu hỏi lạ')
        self.assertTrue(esc)
        self.assertNotIn(ESCALATE, answer)

    def test_escalate_on_llm_error(self):
        with patch.object(self.bot_cls, '_run_agent', side_effect=RuntimeError('LLM down')):
            _answer, esc = self.config._answer(self.company, 'x')
        self.assertTrue(esc, 'lỗi LLM → chuyển nhân viên, không vỡ')

    # ---- BẢO MẬT: ngữ cảnh chỉ của đúng partner ----
    def test_partner_context_scoped_no_leak(self):
        other = self.env['res.partner'].create({'name': 'Cty B khac', 'is_company': True})
        self.env['sale.order'].create({'partner_id': self.company.id})
        self.env['sale.order'].create({'partner_id': other.id})
        ctx_a = self.config._partner_context(self.company)
        self.assertIn('Cty A', ctx_a)
        self.assertNotIn('Cty B khac', ctx_a, 'không được lộ dữ liệu khách hàng khác')

    def test_system_prompt_has_guardrails(self):
        sp = self.config._build_system_prompt(self.company, ['# FAQ\nnội dung'])
        self.assertIn(ESCALATE, sp)
        self.assertIn('không bịa', sp.lower())
        self.assertIn('FAQ', sp)

    # ---- luồng Zalo ----
    def test_zalo_autoreply_sends_and_logs(self):
        with patch.object(self.bot_cls, '_run_agent', return_value='Xin chào, em giúp gì ạ?'), \
             patch.object(self.acc_cls, '_http_post') as send:
            ticket = self.account._handle_inbound('z1', 'alo shop')
        conv = self.env['vct.zalo.conversation'].search(
            [('account_id', '=', self.account.id), ('zalo_user_id', '=', 'z1')])
        self.assertEqual(conv.state, 'bot')
        send.assert_called_once()
        log = self.env['vct.cs.ai.log'].search([('ticket_id', '=', ticket.id)])
        self.assertTrue(log and not log.escalated)
        self.assertTrue(ticket.message_ids.filtered(lambda mm: '🤖' in (mm.body or '')))

    def test_zalo_escalation_switches_to_human(self):
        with patch.object(self.bot_cls, '_run_agent', return_value=ESCALATE), \
             patch.object(self.acc_cls, '_http_post') as send:
            ticket = self.account._handle_inbound('z2', 'tôi muốn gặp người')
        conv = self.env['vct.zalo.conversation'].search(
            [('account_id', '=', self.account.id), ('zalo_user_id', '=', 'z2')])
        self.assertEqual(conv.state, 'human')
        send.assert_not_called()
        log = self.env['vct.cs.ai.log'].search([('ticket_id', '=', ticket.id)])
        self.assertTrue(log.escalated)

    def test_autoreply_off_no_ai(self):
        self.config.zalo_autoreply = False
        with patch.object(self.bot_cls, '_run_agent') as m, \
             patch.object(self.acc_cls, '_http_post'):
            self.account._handle_inbound('z3', 'hello')
        m.assert_not_called()
