# Written for VCT Platform. Not part of Odoo S.A.
import logging
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class VctAiTask(models.Model):
    """A delegated task: describe work in plain language, the AI executes it in
    the background (reusing the vct_llm_assistant agent), and the result +
    status are tracked on the record. Delegate work to the AI — not a chat."""
    _name = 'vct.ai.task'
    _description = 'Việc giao cho Trợ lý AI'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char('Tiêu đề', required=True)
    instruction = fields.Text(
        'Nội dung giao việc', required=True,
        help='Mô tả bằng lời việc cần AI làm, ví dụ: '
             '"Tổng hợp công nợ quá hạn theo khách và soạn email nhắc".')
    state = fields.Selection([
        ('draft', 'Nháp'), ('pending', 'Chờ xử lý'), ('running', 'Đang làm'),
        ('done', 'Xong'), ('failed', 'Lỗi'),
    ], default='draft', required=True, tracking=True, index=True)
    result = fields.Text('Kết quả (thô)', readonly=True)
    result_html = fields.Html(
        'Kết quả', compute='_compute_result_html', sanitize=True,
        help='Kết quả AI đã định dạng (bảng, tiêu đề...).')
    error = fields.Char('Lỗi', readonly=True)
    user_id = fields.Many2one(
        'res.users', 'Người giao', required=True, default=lambda self: self.env.user,
        help='AI chạy theo đúng quyền của người này — không phải quyền admin.')
    use_tools = fields.Boolean(
        'Cho phép thao tác dữ liệu', default=True,
        help='Bật: AI được đọc/tạo/sửa dữ liệu Odoo qua công cụ (theo quyền người giao). '
             'Tắt: chỉ trả lời bằng văn bản.')
    res_model = fields.Char('Model bối cảnh')
    res_id = fields.Integer('ID bản ghi bối cảnh')
    activity_id = fields.Many2one(
        'mail.activity', 'Hoạt động nguồn', ondelete='set null',
        help='Nếu việc được sinh từ một Hoạt động giao cho AI, đánh dấu xong Hoạt động khi hoàn thành.')
    schedule_id = fields.Many2one(
        'vct.ai.task.schedule', 'Lịch định kỳ', ondelete='set null', index='btree_not_null',
        help='Việc này do một lịch định kỳ sinh ra.')
    attachment_count = fields.Integer(compute='_compute_attachment_count')
    started_at = fields.Datetime('Bắt đầu', readonly=True)
    finished_at = fields.Datetime('Kết thúc', readonly=True)

    def _compute_attachment_count(self):
        counts = dict(self.env['ir.attachment']._read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            groupby=['res_id'], aggregates=['__count']))
        for task in self:
            task.attachment_count = counts.get(task.id, 0)

    @api.depends('result')
    def _compute_result_html(self):
        for task in self:
            task.result_html = task._markdown_to_html(task.result)

    # ------------------------------------------------------------------
    # Lightweight markdown -> HTML (no external dependency). Handles the
    # agent's usual output: tables, headings, bullet lists, bold, code, links.
    # AI text is escaped first, so this cannot inject markup.
    # ------------------------------------------------------------------
    def _md_inline(self, text):
        out = escape(text)
        out = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', out)
        out = re.sub(r'`(.+?)`', r'<code>\1</code>', out)
        out = re.sub(r'\[(.+?)\]\((https?:/[^)]+|/[^)]+)\)', r'<a href="\2">\1</a>', out)
        return out

    def _markdown_to_html(self, text):
        if not text:
            return False
        lines = str(text).split('\n')
        html, i = [], 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line.strip():
                i += 1
                continue
            # markdown table: a header row followed by a |---|---| separator
            if (line.lstrip().startswith('|') and i + 1 < len(lines)
                    and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1])):
                header = [c.strip() for c in line.strip().strip('|').split('|')]
                i += 2
                rows = []
                while i < len(lines) and lines[i].lstrip().startswith('|'):
                    rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                    i += 1
                cells = ''.join('<th>%s</th>' % self._md_inline(h) for h in header)
                body = ''
                for row in rows:
                    body += '<tr>%s</tr>' % ''.join('<td>%s</td>' % self._md_inline(c) for c in row)
                html.append('<table class="table table-sm table-bordered">'
                            '<thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (cells, body))
                continue
            if line.startswith('### '):
                html.append('<h4>%s</h4>' % self._md_inline(line[4:]))
            elif line.startswith('## '):
                html.append('<h3>%s</h3>' % self._md_inline(line[3:]))
            elif line.startswith('# '):
                html.append('<h2>%s</h2>' % self._md_inline(line[2:]))
            elif re.match(r'^[-*_]{3,}$', line.strip()):
                html.append('<hr/>')
            elif re.match(r'^\s*[-*]\s+', line):
                items = []
                while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                    items.append('<li>%s</li>' % self._md_inline(re.sub(r'^\s*[-*]\s+', '', lines[i])))
                    i += 1
                html.append('<ul>%s</ul>' % ''.join(items))
                continue
            else:
                html.append('<p>%s</p>' % self._md_inline(line))
            i += 1
        return Markup(''.join(html))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def action_run(self):
        self.filtered(lambda t: t.state in ('draft', 'failed')).write({
            'state': 'pending', 'error': False})
        self._trigger_cron()
        return True

    def action_reset(self):
        self.write({'state': 'draft', 'result': False, 'error': False,
                    'started_at': False, 'finished_at': False})

    def action_attach_result(self):
        """Save the result as a file attached to this task, so it can be shared."""
        self.ensure_one()
        if not self.result:
            return False
        attachment = self.env['ir.attachment'].create({
            'name': _('%s.md') % (self.name or 'ket-qua-ai'),
            'res_model': self._name, 'res_id': self.id,
            'raw': (self.result or '').encode('utf-8'),
            'mimetype': 'text/markdown',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Tệp đính kèm'),
            'res_model': 'ir.attachment', 'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    def _trigger_cron(self):
        cron = self.env.ref('vct_ai_task.ir_cron_run_ai_tasks', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    def _build_prompt(self):
        self.ensure_one()
        if self.res_model and self.res_id and self.res_model in self.env:
            record = self.env[self.res_model].browse(self.res_id).exists()
            if record:
                return _("Bối cảnh — %(model)s #%(id)s: %(name)s\n\nViệc cần làm:\n%(instr)s",
                         model=self.res_model, id=self.res_id,
                         name=record.display_name, instr=self.instruction)
        return self.instruction

    def _execute(self):
        """Run one task through the shared agent, as the delegating user's ACLs."""
        self.ensure_one()
        bot = self.env['mail.bot'].with_user(self.user_id)
        result = bot._run_agent(self._build_prompt(), use_tools=self.use_tools)
        self.write({
            'state': 'done',
            'result': result or _('(AI không trả về nội dung)'),
            'error': False,
            'finished_at': fields.Datetime.now(),
        })
        self.message_post(body=self.result_html or _('Trợ lý AI đã hoàn thành.'))
        # if this task came from an Activity, mark the Activity done
        if self.activity_id:
            self.activity_id.sudo().action_feedback(
                feedback=_('Trợ lý AI đã xử lý.'))

    @api.model
    def _cron_run_pending(self):
        for task in self.search([('state', '=', 'pending')], limit=10):
            task.write({'state': 'running', 'started_at': fields.Datetime.now()})
            try:
                with self.env.cr.savepoint():
                    task._execute()
            except Exception as e:
                task.write({'state': 'failed', 'error': str(e)[:500],
                            'finished_at': fields.Datetime.now()})
                _logger.exception('Việc giao AI %s thất bại', task.id)
