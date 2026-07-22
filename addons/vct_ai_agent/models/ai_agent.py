# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class AiAgent(models.Model):
    """Một tác nhân AI cấu hình được (tương đương Odoo AI): định vai trò + bộ quy tắc
    ứng xử, quyền dùng công cụ ERP (giới hạn an toàn), và các mẫu lệnh nhanh. Chạy
    qua engine sẵn có (mail.bot._run_agent), local Ollama hoặc cloud."""
    _name = 'ai.agent'
    _description = 'Tác nhân AI'
    _order = 'sequence, name'

    name = fields.Char('Tên agent', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer('Màu')
    description = fields.Char('Mô tả ngắn')
    role = fields.Text(
        'Vai trò & quy tắc', required=True,
        help='System prompt: định vai trò, giọng điệu, quy tắc ứng xử và giới hạn của agent.')
    use_tools = fields.Boolean(
        'Cho phép dùng công cụ ERP', default=False,
        help='Bật: agent đọc/ghi dữ liệu Odoo theo QUYỀN của người chạy (giới hạn an toàn: '
             'xoá bị chặn cứng). Tắt: chỉ sinh văn bản, không truy cập dữ liệu.')
    command_ids = fields.One2many('ai.agent.command', 'agent_id', string='Mẫu lệnh')

    def _render_context(self, record):
        """Tóm tắt bản ghi (các trường đơn giản đã có giá trị) để nhồi vào prompt."""
        if not record:
            return ''
        lines = ['Bối cảnh — %s #%s: %s' % (record._name, record.id, record.display_name)]
        count = 0
        for fname, field in record._fields.items():
            if count >= 25 or fname.startswith(('message_', 'activity_', 'website_', 'access_')):
                continue
            try:
                val = record[fname]
            except Exception:
                continue
            if field.type in ('char', 'text', 'selection', 'date', 'datetime',
                               'integer', 'float', 'monetary'):
                if val in (False, '', 0):
                    continue
                if field.type == 'selection' and isinstance(field.selection, list):
                    val = dict(field.selection).get(val, val)
                lines.append('- %s: %s' % (field.string or fname, val))
                count += 1
            elif field.type == 'many2one' and val:
                lines.append('- %s: %s' % (field.string or fname, val.display_name))
                count += 1
        return '\n'.join(lines)

    def run(self, user_text, record=None):
        """Chạy agent với vai trò làm system prompt + ngữ cảnh bản ghi (nếu có)."""
        self.ensure_one()
        prompt = user_text or ''
        if record is not None:
            ctx = self._render_context(record)
            if ctx:
                prompt = '%s\n\nYÊU CẦU: %s' % (ctx, prompt)
        return self.env['mail.bot']._run_agent(
            prompt, system_prompt=self.role, use_tools=self.use_tools)

    def action_open_ask(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.name,
            'res_model': 'ai.ask.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_agent_id': self.id},
        }


class AiAgentCommand(models.Model):
    """Mẫu lệnh nhanh của một agent (Odoo AI: 'command templates')."""
    _name = 'ai.agent.command'
    _description = 'Mẫu lệnh agent'
    _order = 'sequence, id'

    agent_id = fields.Many2one('ai.agent', required=True, ondelete='cascade', index=True)
    name = fields.Char('Tên lệnh', required=True)
    prompt = fields.Text('Nội dung lệnh', required=True,
                         help='Mẫu lệnh gửi agent (có thể mô tả thao tác cần làm).')
    sequence = fields.Integer(default=10)
