# Written for VCT Platform. Not part of Odoo S.A.
import logging

import httpx

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GRAPH = 'https://graph.facebook.com/v20.0'


class FbPost(models.Model):
    """Một bài đăng Facebook đang theo dõi bình luận. Dùng token Page của tài khoản
    Messenger sẵn có để gọi Graph API."""
    _name = 'vct.fb.post'
    _description = 'Bài đăng Facebook'
    _order = 'create_date desc'

    name = fields.Char('Tiêu đề', required=True)
    account_id = fields.Many2one('vct.messenger.account', string='Fanpage', required=True)
    post_id = fields.Char('Post ID', required=True, help='ID bài đăng trên Facebook.')
    message = fields.Text('Nội dung bài')
    active = fields.Boolean(default=True)
    comment_ids = fields.One2many('vct.fb.comment', 'post_id', string='Bình luận')
    comment_count = fields.Integer(compute='_compute_comment_count')

    def _compute_comment_count(self):
        counts = dict(self.env['vct.fb.comment']._read_group(
            [('post_id', 'in', self.ids)], groupby=['post_id'], aggregates=['__count']))
        for post in self:
            post.comment_count = counts.get(post, 0)

    def _http_request(self, method, url, params=None, json_body=None):
        with httpx.Client(timeout=20) as client:
            return client.request(method, url, params=params or {}, json=json_body)

    def action_fetch_comments(self):
        for post in self:
            token = post.account_id.page_access_token
            if not token:
                raise UserError(_('Fanpage chưa có Page Access Token.'))
            try:
                resp = post._http_request('GET', '%s/%s/comments' % (GRAPH, post.post_id), params={
                    'access_token': token, 'fields': 'id,from,message,created_time', 'limit': 100})
                data = resp.json()
            except Exception as e:
                _logger.exception('Kéo bình luận lỗi')
                raise UserError(_('Gọi Facebook lỗi: %s', e))
            for item in data.get('data', []):
                post._upsert_comment(item)

    def _upsert_comment(self, item):
        self.ensure_one()
        Comment = self.env['vct.fb.comment']
        if not item.get('id') or Comment.search_count([('fb_comment_id', '=', item['id'])]):
            return
        frm = item.get('from') or {}
        Comment.create({
            'post_id': self.id, 'fb_comment_id': item['id'],
            'from_name': frm.get('name'), 'from_id': frm.get('id'),
            'message': item.get('message'),
        })

    def action_view_comments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Bình luận'),
            'res_model': 'vct.fb.comment', 'view_mode': 'list,form',
            'domain': [('post_id', '=', self.id)],
        }
