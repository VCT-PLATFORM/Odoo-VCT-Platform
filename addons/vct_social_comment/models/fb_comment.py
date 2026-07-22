# Written for VCT Platform. Not part of Odoo S.A.
import httpx

from odoo import _, api, fields, models
from odoo.exceptions import UserError

GRAPH = 'https://graph.facebook.com/v20.0'

# Từ khoá phát hiện ý định mua trong bình luận (thị trường VN).
_INTENT_WORDS = [
    'giá', 'bao nhiêu', 'bn', 'order', 'đặt', 'inbox', 'ib', 'ship', 'mua',
    'còn không', 'còn ko', 'size', 'mẫu này', 'lấy', 'chốt', 'ship', 'giao',
]


class FbComment(models.Model):
    """Một bình luận Facebook. Tự gắn cờ 'ý định mua' theo từ khoá; có thể trả lời,
    ẩn, và chốt đơn ngay từ bình luận."""
    _name = 'vct.fb.comment'
    _description = 'Bình luận Facebook'
    _order = 'create_date desc'

    post_id = fields.Many2one('vct.fb.post', required=True, ondelete='cascade', index=True)
    account_id = fields.Many2one(related='post_id.account_id')
    fb_comment_id = fields.Char('Comment ID', required=True, index=True)
    from_name = fields.Char('Người bình luận')
    from_id = fields.Char('FB user id')
    message = fields.Text('Nội dung')
    created_time = fields.Char('Thời gian FB')
    is_order_intent = fields.Boolean('Ý định mua', compute='_compute_intent', store=True)
    state = fields.Selection([
        ('new', 'Mới'), ('replied', 'Đã trả lời'), ('hidden', 'Đã ẩn'),
    ], default='new', string='Trạng thái')
    partner_id = fields.Many2one('res.partner', string='Khách hàng')

    _comment_uniq = models.Constraint('UNIQUE(fb_comment_id)', 'Bình luận đã tồn tại.')

    @api.depends('message')
    def _compute_intent(self):
        for comment in self:
            text = (comment.message or '').lower()
            comment.is_order_intent = any(word in text for word in _INTENT_WORDS)

    def _http_request(self, method, url, params=None, json_body=None):
        with httpx.Client(timeout=20) as client:
            return client.request(method, url, params=params or {}, json=json_body)

    def _token(self):
        self.ensure_one()
        token = self.post_id.account_id.page_access_token
        if not token:
            raise UserError(_('Fanpage chưa có Page Access Token.'))
        return token

    def action_hide(self):
        for comment in self:
            comment._http_request('POST', '%s/%s' % (GRAPH, comment.fb_comment_id),
                                  params={'access_token': comment._token(), 'is_hidden': 'true'})
            comment.state = 'hidden'

    def action_open_reply(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vct.fb.comment.reply.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_comment_id': self.id},
        }

    def _get_or_create_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        partner = self.env['res.partner'].create({
            'name': self.from_name or _('Khách FB'),
            'comment': _('Từ bình luận Facebook %s', self.fb_comment_id)})
        self.partner_id = partner
        return partner

    def action_create_order(self):
        self.ensure_one()
        partner = self._get_or_create_partner()
        return self.env['vct.social.order.wizard']._open_for(
            partner, _('FB bình luận: %s', self.from_name or ''))
