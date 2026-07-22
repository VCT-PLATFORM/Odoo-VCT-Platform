# Written for VCT Platform. Not part of Odoo S.A.

from unittest.mock import patch

import httpx

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAiWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.partner_model = cls.env['ir.model'].search([('model', '=', 'res.partner')])
        cls.partner = cls.env['res.partner'].create({'name': 'Công ty ABC'})

    def _ai_action(self, **kw):
        vals = {
            'name': 'AI test', 'model_id': self.partner_model.id,
            'state': 'ai_agent', 'is_ai_workflow': True,
            'ai_prompt': 'Chào {{ name }}', 'ai_use_tools': False,
        }
        vals.update(kw)
        return self.env['ir.actions.server'].create(vals)

    def _run(self, action):
        return action.with_context(
            active_model='res.partner', active_id=self.partner.id,
            active_ids=self.partner.ids).run()

    def test_step_runs_and_logs(self):
        action = self._ai_action()
        with patch.object(self.bot_cls, '_run_agent', return_value='KẾT QUẢ AI') as mocked:
            self._run(action)
        mocked.assert_called_once()
        log = self.env['vct.ai.workflow.log'].search(
            [('action_id', '=', action.id)], limit=1)
        self.assertTrue(log, 'phải ghi 1 nhật ký')
        self.assertTrue(log.success)
        self.assertEqual(log.result, 'KẾT QUẢ AI')
        self.assertEqual(log.res_id, self.partner.id)
        # prompt was rendered: {{ name }} -> partner name, + identity header
        self.assertIn('Công ty ABC', log.prompt)
        self.assertNotIn('{{', log.prompt)
        self.assertIn('res.partner', log.prompt)

    def test_result_written_to_field(self):
        field = self.env['ir.model.fields']._get('res.partner', 'comment')
        action = self._ai_action(ai_result_field_id=field.id)
        with patch.object(self.bot_cls, '_run_agent', return_value='<p>Ghi chú AI</p>'):
            self._run(action)
        self.assertIn('Ghi chú AI', self.partner.comment or '')

    def test_error_is_logged_not_raised(self):
        action = self._ai_action()
        with patch.object(self.bot_cls, '_run_agent', side_effect=ValueError('boom')):
            self._run(action)   # must not raise
        log = self.env['vct.ai.workflow.log'].search(
            [('action_id', '=', action.id)], limit=1)
        self.assertFalse(log.success)
        self.assertIn('boom', log.error)

    def test_prompt_render_dotted_and_unknown(self):
        action = self._ai_action(
            ai_prompt='KH: {{ name }} / thiếu: {{ khong_co_truong }}')
        rendered = action._ai_render_prompt(self.partner)
        self.assertIn('Công ty ABC', rendered)
        self.assertIn('{{ khong_co_truong }}', rendered, 'placeholder lạ giữ nguyên')

    def test_multi_chains_children_sequentially(self):
        """A multi action with two AI children must run both — proof that AI is a
        real node in Odoo's native chaining engine."""
        child1 = self._ai_action(name='Bước 1')
        child2 = self._ai_action(name='Bước 2')
        multi = self.env['ir.actions.server'].create({
            'name': 'Chuỗi 2 bước', 'model_id': self.partner_model.id,
            'state': 'multi', 'is_ai_workflow': True,
            'child_ids': [(6, 0, (child1 | child2).ids)],
        })
        with patch.object(self.bot_cls, '_run_agent', return_value='ok'):
            self._run(multi)
        logs = self.env['vct.ai.workflow.log'].search(
            [('action_id', 'in', (child1 | child2).ids)])
        self.assertEqual(len(logs), 2, 'cả hai bước con phải chạy và ghi log')


@tagged('post_install', '-at_install')
class TestRunAgentReuse(TransactionCase):
    """The workflow step reuses mail.bot._run_agent. Prove it works offline and
    that use_tools=False sends no tools to the model."""

    def test_run_agent_offline_no_tools(self):
        bot = self.env['mail.bot']
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('vct_llm.api_key', 'k')
        ICP.set_param('vct_llm.api_url', 'https://api.anthropic.com/v1/messages')
        with patch.object(type(bot), '_llm_call',
                          return_value={'content': [{'type': 'text', 'text': 'XIN CHÀO'}]}) as m:
            out = bot._run_agent('nói xin chào', use_tools=False)
        self.assertEqual(out, 'XIN CHÀO')
        # _llm_call(api_url, headers, payload) -> payload is 3rd positional arg
        payload = m.call_args[0][2]
        self.assertNotIn('tools', payload, 'use_tools=False không được gửi tools')

    def test_run_agent_missing_key_raises(self):
        bot = self.env['mail.bot']
        self.env['ir.config_parameter'].sudo().set_param('vct_llm.api_key', '')
        with self.assertRaises(Exception):
            bot._run_agent('hi', use_tools=False)


@tagged('post_install', '-at_install')
class TestConditionNode(TransactionCase):
    """The IF node: evaluate a condition per record, route to then/else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.partner_model = cls.env['ir.model'].search([('model', '=', 'res.partner')])
        cls.partner = cls.env['res.partner'].create({'name': 'KH Điều Kiện'})

    def _ai(self, name):
        return self.env['ir.actions.server'].create({
            'name': name, 'model_id': self.partner_model.id, 'state': 'ai_agent',
            'is_ai_workflow': True, 'ai_prompt': 'x', 'ai_use_tools': False})

    def _cond(self, expr, then_a, else_a):
        return self.env['ir.actions.server'].create({
            'name': 'Cond', 'model_id': self.partner_model.id, 'state': 'ai_condition',
            'is_ai_workflow': True, 'condition_expr': expr,
            'then_action_id': then_a.id, 'else_action_id': else_a.id})

    def _run(self, action):
        return action.with_context(
            active_model='res.partner', active_id=self.partner.id,
            active_ids=self.partner.ids).run()

    def _logs(self, action):
        return self.env['vct.ai.workflow.log'].search([('action_id', '=', action.id)])

    def test_true_runs_then_branch(self):
        then_a, else_a = self._ai('THEN'), self._ai('ELSE')
        cond = self._cond("record.name == 'KH Điều Kiện'", then_a, else_a)
        with patch.object(self.bot_cls, '_run_agent', return_value='ok'):
            self._run(cond)
        self.assertTrue(self._logs(then_a), 'nhánh ĐÚNG phải chạy')
        self.assertFalse(self._logs(else_a), 'nhánh SAI không được chạy')
        self.assertIn('ĐÚNG', self._logs(cond).result)

    def test_false_runs_else_branch(self):
        then_a, else_a = self._ai('THEN'), self._ai('ELSE')
        cond = self._cond("record.name == 'KHÔNG KHỚP'", then_a, else_a)
        with patch.object(self.bot_cls, '_run_agent', return_value='ok'):
            self._run(cond)
        self.assertFalse(self._logs(then_a), 'nhánh ĐÚNG không được chạy')
        self.assertTrue(self._logs(else_a), 'nhánh SAI phải chạy')

    def test_bad_expr_logged_not_raised(self):
        then_a, else_a = self._ai('THEN'), self._ai('ELSE')
        cond = self._cond("record.khong_ton_tai.x", then_a, else_a)
        self._run(cond)   # must not raise
        clog = self._logs(cond)
        self.assertFalse(clog.success)
        self.assertTrue(clog.error)


class _FakeResp:
    def __init__(self, status_code=200, text='{"ok": true}'):
        self.status_code = status_code
        self.text = text


@tagged('post_install', '-at_install')
class TestHttpNode(TransactionCase):
    """The HTTP Request node: call an API, store the response for later steps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.srv_cls = type(cls.env['ir.actions.server'])
        cls.partner_model = cls.env['ir.model'].search([('model', '=', 'res.partner')])
        cls.partner = cls.env['res.partner'].create({'name': 'KH HTTP'})

    def _http(self, **kw):
        vals = {'name': 'HTTP', 'model_id': self.partner_model.id, 'state': 'ai_http',
                'is_ai_workflow': True, 'http_method': 'get',
                'http_url': 'https://vidu.test/{{ name }}'}
        vals.update(kw)
        return self.env['ir.actions.server'].create(vals)

    def _run(self, action):
        return action.with_context(
            active_model='res.partner', active_id=self.partner.id,
            active_ids=self.partner.ids).run()

    def _log(self, action):
        return self.env['vct.ai.workflow.log'].search([('action_id', '=', action.id)], limit=1)

    def test_get_stores_response_and_substitutes_url(self):
        field = self.env['ir.model.fields']._get('res.partner', 'comment')
        action = self._http(http_result_field_id=field.id)
        captured = {}

        def fake_call(self_srv, method, url, **kwargs):
            captured['method'], captured['url'] = method, url
            return _FakeResp(200, 'PHẢN HỒI OK')
        with patch.object(self.srv_cls, '_http_call', autospec=True, side_effect=fake_call):
            self._run(action)
        self.assertEqual(captured['url'], 'https://vidu.test/KH HTTP', 'URL phải thay {{ name }}')
        self.assertIn('PHẢN HỒI OK', self.partner.comment or '')
        self.assertTrue(self._log(action).success)

    def test_http_error_status_logged_failure(self):
        action = self._http()
        with patch.object(self.srv_cls, '_http_call', autospec=True,
                          return_value=_FakeResp(500, 'Server Error')):
            self._run(action)
        log = self._log(action)
        self.assertFalse(log.success)
        self.assertIn('500', log.error)

    def test_post_sends_json_body_substituted(self):
        action = self._http(http_method='post', http_body='{"ten": "{{ name }}"}')
        captured = {}

        def fake_call(self_srv, method, url, **kwargs):
            captured.update(kwargs)
            captured['method'] = method
            return _FakeResp(200, 'ok')
        with patch.object(self.srv_cls, '_http_call', autospec=True, side_effect=fake_call):
            self._run(action)
        self.assertEqual(captured['method'], 'post')
        self.assertEqual(captured.get('json'), {'ten': 'KH HTTP'}, 'body JSON phải parse + thay {{ }}')

    def test_network_error_logged_not_raised(self):
        action = self._http()
        with patch.object(self.srv_cls, '_http_call', autospec=True,
                          side_effect=httpx.ConnectError('không nối được')):
            self._run(action)   # must not raise
        log = self._log(action)
        self.assertFalse(log.success)
        self.assertIn('không nối được', log.error)
