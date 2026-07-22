# Written for VCT Platform. Not part of Odoo S.A.
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html


class AiAskWizard(models.TransientModel):
    """'Hỏi AI' theo ngữ cảnh trên bất kỳ bản ghi nào: chọn agent, đặt câu hỏi,
    nhận trả lời — tuỳ chọn ghi vào một trường hoặc đăng vào chatter."""
    _name = 'ai.ask.wizard'
    _description = 'Hỏi AI'

    agent_id = fields.Many2one('ai.agent', string='Agent', required=True)
    res_model = fields.Char('Model')
    res_id = fields.Integer('ID bản ghi')
    record_name = fields.Char(compute='_compute_record_name')
    command_id = fields.Many2one(
        'ai.agent.command', string='Mẫu lệnh', domain="[('agent_id','=',agent_id)]")
    question = fields.Text('Câu hỏi / yêu cầu')
    result = fields.Text('Kết quả AI', readonly=True)
    result_field_id = fields.Many2one(
        'ir.model.fields', string='Ghi kết quả vào trường',
        domain="[('model','=',res_model),('ttype','in',['char','text','html'])]")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.setdefault('res_model', self.env.context.get('active_model'))
        res.setdefault('res_id', self.env.context.get('active_id'))
        return res

    def _record(self):
        self.ensure_one()
        if self.res_model and self.res_id and self.res_model in self.env:
            return self.env[self.res_model].browse(self.res_id).exists()
        return self.env['ai.agent'].browse()  # empty recordset ~ None

    @api.depends('res_model', 'res_id')
    def _compute_record_name(self):
        for wiz in self:
            rec = wiz._record()
            wiz.record_name = rec.display_name if rec else ''

    @api.onchange('command_id')
    def _onchange_command_id(self):
        if self.command_id and not self.question:
            self.question = self.command_id.prompt

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': 'ai.ask.wizard',
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
            'name': _('Hỏi AI'),
        }

    def action_ask(self):
        self.ensure_one()
        if not self.question:
            raise UserError(_('Nhập câu hỏi hoặc chọn một mẫu lệnh.'))
        record = self._record()
        self.result = self.agent_id.run(self.question, record=record or None)
        return self._reopen()

    def action_post_chatter(self):
        self.ensure_one()
        record = self._record()
        if record and self.result and hasattr(record, 'message_post'):
            record.message_post(body=plaintext2html(self.result))
        return {'type': 'ir.actions.act_window_close'}

    def action_write_field(self):
        self.ensure_one()
        record = self._record()
        if not (record and self.result_field_id and self.result):
            raise UserError(_('Cần có kết quả và chọn trường để ghi.'))
        record.write({self.result_field_id.name: self.result})
        return {'type': 'ir.actions.act_window_close'}
