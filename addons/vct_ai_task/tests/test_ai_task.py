# Written for VCT Platform. Not part of Odoo S.A.

from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAiTask(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.Task = cls.env['vct.ai.task']

    def _task(self, **kw):
        vals = {'name': 'Việc thử', 'instruction': 'Tổng hợp công nợ quá hạn'}
        vals.update(kw)
        return self.Task.create(vals)

    # ---- core execution --------------------------------------------------
    def test_run_stores_result_and_marks_done(self):
        task = self._task()
        task.action_run()
        self.assertEqual(task.state, 'pending')
        with patch.object(self.bot_cls, '_run_agent', return_value='ĐÃ XONG VIỆC') as mocked:
            self.Task._cron_run_pending()
        mocked.assert_called_once()
        self.assertEqual(task.state, 'done')
        self.assertEqual(task.result, 'ĐÃ XONG VIỆC')
        self.assertTrue(task.finished_at)

    def test_failure_is_logged_not_raised(self):
        task = self._task()
        task.action_run()
        with patch.object(self.bot_cls, '_run_agent', side_effect=ValueError('LLM sập')):
            self.Task._cron_run_pending()
        self.assertEqual(task.state, 'failed')
        self.assertIn('LLM sập', task.error)

    def test_use_tools_flag_passed_through(self):
        task = self._task(use_tools=False)
        task.action_run()
        with patch.object(self.bot_cls, '_run_agent', return_value='ok') as mocked:
            self.Task._cron_run_pending()
        self.assertEqual(mocked.call_args.kwargs.get('use_tools'), False)

    def test_prompt_includes_record_context(self):
        partner = self.env['res.partner'].create({'name': 'Khách Bối Cảnh'})
        task = self._task(res_model='res.partner', res_id=partner.id)
        prompt = task._build_prompt()
        self.assertIn('Khách Bối Cảnh', prompt)
        self.assertIn('res.partner', prompt)

    def test_runs_as_delegating_user(self):
        task = self._task()
        task.action_run()
        captured = {}

        def _spy(self_bot, *a, **k):
            captured['uid'] = self_bot.env.uid
            return 'ok'
        with patch.object(self.bot_cls, '_run_agent', autospec=True, side_effect=_spy):
            self.Task._cron_run_pending()
        self.assertEqual(captured.get('uid'), task.user_id.id)

    # ---- result rendering + attachment ----------------------------------
    def test_markdown_result_renders_html(self):
        task = self._task()
        task.write({'result': '## Báo cáo\n\n| Khách | Nợ |\n|---|---|\n| A | 100 |\n\n**Quan trọng**'})
        html = str(task.result_html)
        self.assertIn('<h3>Báo cáo</h3>', html)
        self.assertIn('<table', html)
        self.assertIn('<strong>Quan trọng</strong>', html)

    def test_markdown_escapes_injection(self):
        task = self._task()
        task.write({'result': 'Xin chào <script>alert(1)</script>'})
        html = str(task.result_html)
        self.assertNotIn('<script>', html, 'nội dung AI phải được escape, không chèn thẻ')

    def test_attach_result_creates_file(self):
        task = self._task()
        task.write({'result': 'Nội dung kết quả'})
        task.action_attach_result()
        att = self.env['ir.attachment'].search(
            [('res_model', '=', 'vct.ai.task'), ('res_id', '=', task.id)])
        self.assertTrue(att, 'phải tạo tệp đính kèm kết quả')
        self.assertEqual(task.attachment_count, 1)

    # ---- recurring schedule ---------------------------------------------
    def test_schedule_spawns_task_and_reschedules(self):
        past = fields.Datetime.subtract(fields.Datetime.now(), hours=1)
        sched = self.env['vct.ai.task.schedule'].create({
            'name': 'Mỗi ngày', 'instruction': 'Tổng hợp báo cáo',
            'interval_number': 1, 'interval_type': 'days', 'next_run': past,
        })
        self.env['vct.ai.task.schedule']._cron_run_schedules()
        self.assertEqual(sched.run_count, 1)
        self.assertGreater(sched.next_run, fields.Datetime.now(), 'next_run phải đẩy về tương lai')
        tasks = self.Task.search([('schedule_id', '=', sched.id)])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.state, 'pending', 'việc sinh ra phải được đưa vào hàng chờ')

    # ---- activity integration -------------------------------------------
    def test_activity_of_ai_type_spawns_task(self):
        partner = self.env['res.partner'].create({'name': 'KH Hoạt động'})
        partner.activity_schedule(
            'vct_ai_task.mail_activity_type_ai',
            summary='Tóm tắt khách hàng', note='<p>Xem lịch sử giao dịch</p>')
        task = self.Task.search([('res_model', '=', 'res.partner'), ('res_id', '=', partner.id)])
        self.assertTrue(task, 'giao Hoạt động cho AI phải sinh ra việc')
        self.assertTrue(task.activity_id, 'việc phải liên kết ngược tới Hoạt động')
        self.assertIn('Tóm tắt khách hàng', task.instruction)
