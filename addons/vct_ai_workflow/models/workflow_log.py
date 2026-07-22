# Written for VCT Platform. Not part of Odoo S.A.
from odoo import api, fields, models


class VctAiWorkflowLog(models.Model):
    _name = 'vct.ai.workflow.log'
    _description = 'Nhật ký thực thi Workflow AI'
    _order = 'id desc'
    _rec_name = 'action_id'

    action_id = fields.Many2one(
        'ir.actions.server', string='Bước AI', ondelete='cascade', index=True)
    res_model = fields.Char(string='Model')
    res_id = fields.Integer(string='ID bản ghi')
    record_ref = fields.Reference(
        selection='_selection_target_model', string='Bản ghi',
        compute='_compute_record_ref')
    prompt = fields.Text(string='Chỉ dẫn gửi AI')
    result = fields.Text(string='Kết quả AI')
    success = fields.Boolean(string='Thành công')
    error = fields.Char(string='Lỗi')

    @api.model
    def _selection_target_model(self):
        return [(m.model, m.name) for m in self.env['ir.model'].sudo().search([])]

    def _compute_record_ref(self):
        for log in self:
            log.record_ref = (f'{log.res_model},{log.res_id}'
                              if log.res_model and log.res_id else False)
