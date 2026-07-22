# Written for VCT Platform. Not part of Odoo S.A.

import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAgentTools(TransactionCase):
    """The tool executor is the security surface: an LLM (steerable by prompt
    injection) drives it. These prove the dangerous doors stay shut."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot = cls.env['mail.bot']
        cls.env_ = cls.env  # tools run with the caller's ACLs

    def _run(self, tool, args):
        return self.bot._execute_agent_tool(self.env, tool, args)

    # ---- security: destructive doors ----------------------------------
    def test_unlink_is_blocked(self):
        partner = self.env['res.partner'].create({'name': 'Xoá thử AI'})
        res = self._run('call_button_method',
                        {'model': 'res.partner', 'method': 'unlink', 'ids': partner.ids})
        self.assertIn('an toàn', res, 'unlink phải bị chặn với thông báo an toàn')
        self.assertTrue(partner.exists(), 'bản ghi KHÔNG được bị xoá')

    def test_private_method_blocked(self):
        res = self._run('call_button_method',
                        {'model': 'res.partner', 'method': '_compute_display_name', 'ids': []})
        self.assertIn('an toàn', res)

    def test_non_action_method_blocked(self):
        # 'read' is in the denylist and lacks an allowed prefix
        res = self._run('call_button_method',
                        {'model': 'res.partner', 'method': 'read', 'ids': []})
        self.assertIn('an toàn', res)

    def test_allowed_prefix_passes_the_guard(self):
        """A method with an allowed prefix must clear the safety gate — proven by
        getting the 'does not exist' error, not the 'blocked' one."""
        res = self._run('call_button_method',
                        {'model': 'res.partner', 'method': 'action_no_such', 'ids': []})
        self.assertNotIn('an toàn', res)
        self.assertIn('does not exist', res)

    def test_bad_domain_errors_instead_of_reading_everything(self):
        res = self._run('search_read_records',
                        {'model': 'res.partner', 'domain': 'garbage{not a domain'})
        self.assertIn('không hợp lệ', res, 'domain hỏng phải báo lỗi, không đọc cả bảng')

    # ---- capability: the four focuses ---------------------------------
    def test_read_group_aggregates(self):
        res = self._run('read_group',
                        {'model': 'ir.model', 'groupby': ['transient'], 'aggregates': ['__count']})
        rows = json.loads(res)
        self.assertTrue(rows and '__count' in rows[0], 'read_group phải trả về số đếm theo nhóm')

    def test_find_menu(self):
        menu = self.env['ir.ui.menu'].create({'name': 'Menu Kiểm Thử AI XYZ'})
        res = self._run('find_menu', {'search': 'Kiểm Thử AI XYZ'})
        self.assertIn('Kiểm Thử AI XYZ', res)
        self.assertIn(menu.name, json.loads(res)[0]['menu'])

    def test_get_record_url(self):
        res = self._run('get_record_url', {'model': 'res.partner', 'id': 7})
        self.assertEqual(res, '/web#id=7&model=res.partner&view_type=form')

    def test_create_and_write_work(self):
        created = json.loads(self._run('create_record',
                             {'model': 'res.partner', 'values': {'name': 'AI tạo'}}))
        self.assertEqual(created['status'], 'success')
        pid = created['id']
        wrote = json.loads(self._run('write_record',
                            {'model': 'res.partner', 'ids': [pid], 'values': {'phone': '0900'}}))
        self.assertEqual(wrote['status'], 'success')
        self.assertEqual(self.env['res.partner'].browse(pid).phone, '0900')


@tagged('post_install', '-at_install')
class TestAgentAsync(TransactionCase):

    def setUp(self):
        super().setUp()
        self.bot = self.env['mail.bot']
        self.odoobot = self.env.ref('base.partner_root')
        # a distinct human, because the test env user's partner IS partner_root
        self.human = self.env['res.users'].create({
            'name': 'NV Chat AI', 'login': 'nv_chat_ai',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        # a real DM: a chat channel with odoobot as a member. This is the
        # primary way users talk to the assistant (core only detects the bot in
        # chats, not group channels — see mail_bot._get_answer). The creator
        # (our human) is auto-added, so odoobot is the only explicit member.
        self.channel = self.env['discuss.channel'].with_user(self.human).create({
            'name': 'DM Trợ lý AI', 'channel_type': 'chat',
            'channel_member_ids': [(0, 0, {'partner_id': self.odoobot.id})],
        })

    def test_dm_message_enqueues_a_job(self):
        before = self.env['vct.llm.job'].search_count([])
        self.channel.with_user(self.human).message_post(
            body='Có bao nhiêu đối tác?',
            message_type='comment', subtype_xmlid='mail.mt_comment')
        jobs = self.env['vct.llm.job'].search([('channel_id', '=', self.channel.id)])
        self.assertEqual(len(jobs), 1, 'nhắn cho bot trong DM phải tạo đúng 1 job')
        self.assertEqual(jobs.state, 'pending')
        self.assertEqual(jobs.user_id, self.human, 'job chạy theo quyền người chat')
        self.assertEqual(self.env['vct.llm.job'].search_count([]), before + 1)

    def test_bot_own_message_does_not_enqueue(self):
        self.channel.message_post(
            author_id=self.odoobot.id, body='Tôi là bot',
            message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertFalse(
            self.env['vct.llm.job'].search([('channel_id', '=', self.channel.id)]),
            'tin nhắn của chính bot không được tạo job (tránh vòng lặp vô hạn)')

    def test_agent_loop_runs_tool_then_replies_offline(self):
        """Drive the whole loop with a scripted model — no network. Proves a
        tool_use round-trips into a real tool call and a posted reply."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('vct_llm.api_key', 'test-key')
        ICP.set_param('vct_llm.api_url', 'https://api.anthropic.com/v1/messages')
        ICP.set_param('vct_llm.model_name', 'claude-sonnet-5')
        self.channel.with_user(self.human).message_post(
            body='Có bao nhiêu model?', message_type='comment',
            subtype_xmlid='mail.mt_comment')

        scripted = [
            {'content': [{'type': 'tool_use', 'id': 't1',
                          'name': 'read_group',
                          'input': {'model': 'ir.model', 'aggregates': ['__count']}}]},
            {'content': [{'type': 'text', 'text': 'Hệ thống có nhiều model.'}]},
        ]
        with patch.object(type(self.bot), '_llm_call', side_effect=scripted) as mocked:
            self.bot._process_channel(self.channel)

        self.assertEqual(mocked.call_count, 2, 'loop: 1 lần gọi tool + 1 lần trả lời')
        last = self.channel.message_ids.sorted('id')[-1]
        self.assertEqual(last.author_id, self.odoobot)
        self.assertIn('nhiều model', last.body)
