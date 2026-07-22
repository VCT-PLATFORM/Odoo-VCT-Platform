# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, api, models
from odoo.tools import html2plaintext


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        ai_type = self.env.ref('vct_ai_task.mail_activity_type_ai', raise_if_not_found=False)
        if ai_type:
            for act in activities.filtered(lambda a: a.activity_type_id == ai_type):
                act._delegate_to_ai()
        return activities

    def _delegate_to_ai(self):
        """Spawn a delegated AI task from this activity; the task marks the
        activity done when the AI finishes."""
        self.ensure_one()
        parts = [p for p in (self.summary or '', html2plaintext(self.note or '')) if p.strip()]
        instruction = '\n'.join(parts).strip() or _('Xử lý hoạt động này.')
        task = self.env['vct.ai.task'].sudo().create({
            'name': self.summary or _('Hoạt động giao AI'),
            'instruction': instruction,
            'res_model': self.res_model,
            'res_id': self.res_id,
            'user_id': (self.user_id or self.create_uid).id,
            'activity_id': self.id,
        })
        task.action_run()
        return task
