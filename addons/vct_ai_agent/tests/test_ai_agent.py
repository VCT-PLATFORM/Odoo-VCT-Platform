# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAiAgent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.agent_gen = cls.env.ref('vct_ai_agent.agent_general')
        cls.agent_data = cls.env.ref('vct_ai_agent.agent_data')
        cls.partner = cls.env['res.partner'].create({'name': 'Khách Bối Cảnh', 'phone': '0900000000'})

    # ---- agent.run ----
    def test_run_passes_role_and_tools(self):
        captured = {}

        def spy(self_bot, user_text, system_prompt=None, use_tools=True):
            captured.update(user_text=user_text, system_prompt=system_prompt, use_tools=use_tools)
            return 'OK'
        with patch.object(self.bot_cls, '_run_agent', autospec=True, side_effect=spy):
            out = self.agent_gen.run('xin chào')
        self.assertEqual(out, 'OK')
        self.assertEqual(captured['system_prompt'], self.agent_gen.role)
        self.assertFalse(captured['use_tools'], 'agent chung không dùng tool')

    def test_run_injects_record_context(self):
        captured = {}

        def spy(self_bot, user_text, system_prompt=None, use_tools=True):
            captured['user_text'] = user_text
            return 'OK'
        with patch.object(self.bot_cls, '_run_agent', autospec=True, side_effect=spy):
            self.agent_data.run('phân tích', record=self.partner)
        self.assertIn('Khách Bối Cảnh', captured['user_text'], 'prompt phải kèm ngữ cảnh bản ghi')
        self.assertIn('phân tích', captured['user_text'])

    def test_data_agent_uses_tools(self):
        with patch.object(self.bot_cls, '_run_agent', autospec=True, return_value='x') as m:
            self.agent_data.run('liệt kê')
        self.assertTrue(m.call_args.kwargs.get('use_tools'), 'chuyên viên dữ liệu bật tool')

    # ---- wizard ----
    def _wizard(self, **kw):
        vals = {'agent_id': self.agent_gen.id}
        vals.update(kw)
        return self.env['ai.ask.wizard'].create(vals)

    def test_wizard_ask_sets_result(self):
        wiz = self._wizard(question='2+2?')
        with patch.object(self.bot_cls, '_run_agent', autospec=True, return_value='Bằng 4.'):
            wiz.action_ask()
        self.assertEqual(wiz.result, 'Bằng 4.')

    def test_wizard_requires_question(self):
        wiz = self._wizard()
        with self.assertRaises(UserError):
            wiz.action_ask()

    def test_wizard_post_to_chatter(self):
        wiz = self._wizard(res_model='res.partner', res_id=self.partner.id, question='q')
        with patch.object(self.bot_cls, '_run_agent', autospec=True, return_value='Ghi chú AI'):
            wiz.action_ask()
        wiz.action_post_chatter()
        self.assertTrue(self.partner.message_ids.filtered(lambda m: 'Ghi chú AI' in (m.body or '')))

    def test_wizard_write_field(self):
        field = self.env['ir.model.fields']._get('res.partner', 'comment')
        wiz = self._wizard(res_model='res.partner', res_id=self.partner.id,
                           question='q', result_field_id=field.id)
        with patch.object(self.bot_cls, '_run_agent', autospec=True, return_value='Mô tả mới'):
            wiz.action_ask()
        wiz.action_write_field()
        self.assertIn('Mô tả mới', self.partner.comment or '')

    # ---- seeded actions ----
    def test_ask_action_seeded_on_partner(self):
        act = self.env['ir.actions.server'].search([
            ('name', '=', '🤖 Hỏi AI'), ('binding_model_id.model', '=', 'res.partner')])
        self.assertTrue(act, 'post_init phải gắn Hỏi AI trên res.partner')
