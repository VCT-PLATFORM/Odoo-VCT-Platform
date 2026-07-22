# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCopilotQa(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_cls = type(cls.env['mail.bot'])
        cls.team = cls.env['helpdesk.team'].create({'name': 'CP team'})
        cls.partner = cls.env['res.partner'].create({'name': 'KH CP'})

    def _ticket_with_chat(self):
        t = self.env['helpdesk.ticket'].create({
            'name': 'Đơn chưa nhận', 'team_id': self.team.id, 'partner_id': self.partner.id,
            'description': '<p>Khách hỏi đơn hàng</p>'})
        t.message_post(body='Đơn của tôi đâu?', message_type='comment', subtype_xmlid='mail.mt_comment')
        return t

    # ---- Copilot ----
    def test_suggest_fills_result(self):
        t = self._ticket_with_chat()
        with patch.object(self.bot_cls, '_run_agent', return_value='Dạ đơn đang giao ạ.') as m:
            action = self.env['vct.cs.copilot']._open_for(t, 'suggest')
        self.assertEqual(m.call_args.kwargs.get('use_tools'), False)
        wiz = self.env['vct.cs.copilot'].browse(action['res_id'])
        self.assertIn('đang giao', wiz.result)

    def test_rewrite_uses_draft(self):
        t = self._ticket_with_chat()
        wiz = self.env['vct.cs.copilot'].create({
            'ticket_id': t.id, 'mode': 'rewrite', 'tone': 'formal', 'draft': 'ok chờ nhé'})
        with patch.object(self.bot_cls, '_run_agent', return_value='Kính gửi Quý khách...') as m:
            wiz.action_generate()
        self.assertEqual(m.call_args[0][0], 'ok chờ nhé', 'gửi đúng bản nháp cho AI viết lại')
        self.assertIn('Kính gửi', wiz.result)

    def test_post_reply_creates_comment(self):
        t = self._ticket_with_chat()
        wiz = self.env['vct.cs.copilot'].create({
            'ticket_id': t.id, 'mode': 'suggest', 'result': 'Cảm ơn anh đã liên hệ.'})
        wiz.action_post_reply()
        self.assertTrue(t.message_ids.filtered(lambda mm: 'Cảm ơn anh' in (mm.body or '')))

    # ---- AutoQA ----
    def test_qa_scores_from_json(self):
        t = self._ticket_with_chat()
        with patch.object(self.bot_cls, '_run_agent',
                          return_value='Đây: {"diem": 85, "nguy_co": false, "nhan_xet": "Tốt"}'):
            score = self.env['vct.cs.qa.score']._generate_for(t)
        self.assertTrue(score)
        self.assertEqual(score.score, 85)
        self.assertFalse(score.at_risk)
        self.assertEqual(score.notes, 'Tốt')

    def test_qa_flags_risk(self):
        t = self._ticket_with_chat()
        with patch.object(self.bot_cls, '_run_agent',
                          return_value='{"diem": 30, "nguy_co": true, "nhan_xet": "Khách bức xúc"}'):
            score = self.env['vct.cs.qa.score']._generate_for(t)
        self.assertTrue(score.at_risk)

    def test_qa_no_conversation_returns_false(self):
        t = self.env['helpdesk.ticket'].create({'name': 'trống', 'team_id': self.team.id})
        with patch.object(self.bot_cls, '_run_agent', return_value='{}') as m:
            score = self.env['vct.cs.qa.score']._generate_for(t)
        self.assertFalse(score, 'không có hội thoại → không chấm')
        m.assert_not_called()

    def test_qa_llm_error_returns_false(self):
        t = self._ticket_with_chat()
        with patch.object(self.bot_cls, '_run_agent', side_effect=RuntimeError('down')):
            score = self.env['vct.cs.qa.score']._generate_for(t)
        self.assertFalse(score)
