# Written for VCT Platform. Not part of Odoo S.A.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class VctLlmJob(models.Model):
    _name = 'vct.llm.job'
    _description = 'Hàng đợi xử lý Trợ lý AI'
    _order = 'id'

    channel_id = fields.Many2one('discuss.channel', required=True, ondelete='cascade')
    # whose ACLs the agent runs under — the person who chatted, never sudo/admin
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    state = fields.Selection([
        ('pending', 'Chờ xử lý'), ('done', 'Xong'), ('failed', 'Lỗi'),
    ], default='pending', required=True, index=True)
    error = fields.Char()

    def _trigger_cron(self):
        cron = self.env.ref('vct_llm_assistant.ir_cron_vct_llm_process',
                            raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return self

    @api.model
    def _cron_process_jobs(self):
        for job in self.search([('state', '=', 'pending')], limit=20):
            try:
                with self.env.cr.savepoint():   # one bad job never rolls back the rest
                    self.env['mail.bot'].with_user(job.user_id)._process_channel(job.channel_id)
                job.state = 'done'
            except Exception as e:
                job.state = 'failed'
                job.error = str(e)[:500]
                _logger.exception("Trợ lý AI: job %s thất bại", job.id)
