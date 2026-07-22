# Written for VCT Platform. Not part of Odoo S.A.
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@tagged('post_install', '-at_install')
class TestSocialComment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.post_cls = type(cls.env['vct.fb.post'])
        cls.comment_cls = type(cls.env['vct.fb.comment'])
        cls.acc = cls.env['vct.messenger.account'].create({
            'name': 'Page', 'page_id': 'PCM', 'page_access_token': 'TOK'})
        cls.post = cls.env['vct.fb.post'].create({
            'name': 'Bài 1', 'account_id': cls.acc.id, 'post_id': 'POST1'})
        cls.Comment = cls.env['vct.fb.comment']

    def _comment(self, cid, message='hello', name='An'):
        return self.Comment.create({
            'post_id': self.post.id, 'fb_comment_id': cid, 'message': message, 'from_name': name})

    def test_fetch_creates_comments_with_intent(self):
        resp = _Resp({'data': [
            {'id': 'c1', 'from': {'id': 'u1', 'name': 'An'}, 'message': 'giá bao nhiêu shop?'},
            {'id': 'c2', 'from': {'id': 'u2', 'name': 'Bình'}, 'message': 'đẹp quá'},
        ]})
        with patch.object(self.post_cls, '_http_request', autospec=True, return_value=resp):
            self.post.action_fetch_comments()
        comments = self.Comment.search([('post_id', '=', self.post.id)])
        self.assertEqual(len(comments), 2)
        self.assertTrue(comments.filtered(lambda c: c.fb_comment_id == 'c1').is_order_intent)
        self.assertFalse(comments.filtered(lambda c: c.fb_comment_id == 'c2').is_order_intent)

    def test_intent_detection(self):
        self.assertTrue(self._comment('i1', 'cho mình đặt 1 cái').is_order_intent)
        self.assertFalse(self._comment('i2', 'quá đẹp luôn').is_order_intent)

    def test_hide(self):
        comment = self._comment('h1')
        with patch.object(self.comment_cls, '_http_request', autospec=True, return_value=_Resp({})):
            comment.action_hide()
        self.assertEqual(comment.state, 'hidden')

    def test_reply_wizard(self):
        comment = self._comment('r1')
        wiz = self.env['vct.fb.comment.reply.wizard'].create({
            'comment_id': comment.id, 'message': 'Dạ 150k ạ'})
        with patch.object(self.comment_cls, '_http_request', autospec=True, return_value=_Resp({})):
            wiz.action_send()
        self.assertEqual(comment.state, 'replied')

    def test_create_order_from_comment(self):
        comment = self._comment('o1', 'giá nhiêu ạ', name='Chị Hoa')
        action = comment.action_create_order()
        self.assertEqual(action['res_model'], 'vct.social.order.wizard')
        self.assertTrue(comment.partner_id, 'phải tạo khách từ người bình luận')
        wiz = self.env['vct.social.order.wizard'].browse(action['res_id'])
        self.assertEqual(wiz.partner_id, comment.partner_id)
