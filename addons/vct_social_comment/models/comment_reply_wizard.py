# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models

GRAPH = 'https://graph.facebook.com/v20.0'


class CommentReplyWizard(models.TransientModel):
    _name = 'vct.fb.comment.reply.wizard'
    _description = 'Trả lời bình luận'

    comment_id = fields.Many2one('vct.fb.comment', required=True)
    message = fields.Text('Nội dung trả lời', required=True)

    def action_send(self):
        self.ensure_one()
        comment = self.comment_id
        comment._http_request(
            'POST', '%s/%s/comments' % (GRAPH, comment.fb_comment_id),
            params={'access_token': comment._token()}, json_body={'message': self.message})
        comment.state = 'replied'
        return {'type': 'ir.actions.act_window_close'}
