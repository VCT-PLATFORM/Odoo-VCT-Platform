# Written for VCT Platform. Not part of Odoo S.A.
import json
import logging
import re

import httpx

from odoo import _, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# {{ field }} or {{ partner_id.name }} — substituted from the record
_PLACEHOLDER = re.compile(r'\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}')


class IrActionsServer(models.Model):
    """Adds AI-workflow node types to Odoo's server actions the way sms/mail add
    theirs. AI, branching and HTTP become first-class nodes in the native
    automation engine — triggers (base_automation), scheduling (ir.cron) and
    sequential chaining (child_ids) all come for free."""
    _inherit = 'ir.actions.server'

    state = fields.Selection(
        selection_add=[
            ('ai_agent', 'Bước AI Agent'),
            ('ai_condition', 'Điều kiện (rẽ nhánh)'),
            ('ai_http', 'Gọi HTTP (API ngoài)'),
        ],
        ondelete={'ai_agent': 'cascade', 'ai_condition': 'cascade', 'ai_http': 'cascade'})
    is_ai_workflow = fields.Boolean(
        string='Là workflow AI', default=False,
        help='Đánh dấu để hiện trong màn hình Workflow AI.')
    ai_prompt = fields.Text(
        string='Chỉ dẫn cho AI',
        help='Yêu cầu gửi cho AI. Có thể chèn dữ liệu bản ghi bằng {{ tên_trường }}, '
             'ví dụ {{ name }} hoặc {{ partner_id.name }}.')
    ai_use_tools = fields.Boolean(
        string='Cho phép AI dùng công cụ', default=False,
        help='Bật: bước AI có thể đọc/ghi dữ liệu Odoo qua công cụ của agent '
             '(theo quyền của người chạy). Tắt: chỉ sinh văn bản từ chỉ dẫn.')
    ai_result_field_id = fields.Many2one(
        'ir.model.fields', string='Lưu kết quả vào trường',
        domain="[('model_id','=',model_id),('ttype','in',['char','text','html'])]",
        ondelete='set null',
        help='Tuỳ chọn: ghi văn bản AI trả về vào trường này trên bản ghi.')

    # ---- Điều kiện (rẽ nhánh) — n8n IF node ----
    condition_expr = fields.Char(
        string='Điều kiện',
        help="Biểu thức Python trên 'record', ví dụ: record.amount_total > 10000000")
    then_action_id = fields.Many2one(
        'ir.actions.server', string='Nếu ĐÚNG → chạy', ondelete='set null',
        domain="[('id','!=',id)]")
    else_action_id = fields.Many2one(
        'ir.actions.server', string='Nếu SAI → chạy', ondelete='set null',
        domain="[('id','!=',id)]")

    # ---- HTTP Request — n8n HTTP node ----
    http_url = fields.Char(string='URL', help='Hỗ trợ {{ tên_trường }}.')
    http_method = fields.Selection([
        ('get', 'GET'), ('post', 'POST'), ('put', 'PUT'),
        ('patch', 'PATCH'), ('delete', 'DELETE')],
        string='Phương thức', default='get')
    http_headers = fields.Text(string='Headers (JSON)', help='Ví dụ {"Authorization": "Bearer ..."}')
    http_body = fields.Text(string='Body (JSON)', help='Hỗ trợ {{ tên_trường }}.')
    http_result_field_id = fields.Many2one(
        'ir.model.fields', string='Lưu phản hồi vào trường',
        domain="[('model_id','=',model_id),('ttype','in',['char','text'])]", ondelete='set null',
        help='Ghi nội dung phản hồi HTTP vào trường này để bước sau dùng lại.')
    http_timeout = fields.Integer(string='Timeout (giây)', default=30)

    def _ai_substitute(self, text, record):
        """Replace {{ path }} with values from the record."""
        def repl(match):
            value = record
            try:
                for part in match.group(1).split('.'):
                    value = getattr(value, part)
                return str(value)
            except Exception:
                return match.group(0)   # leave unknown placeholders untouched
        return _PLACEHOLDER.sub(repl, text or '')

    def _ai_render_prompt(self, record):
        header = _("Bản ghi: %(model)s #%(id)s — %(name)s\n",
                   model=record._name, id=record.id, name=record.display_name)
        return header + self._ai_substitute(self.ai_prompt or '', record)

    def _log(self, record, prompt, result, success, error=False):
        self.env['vct.ai.workflow.log'].sudo().create({
            'action_id': self.id, 'res_model': record._name, 'res_id': record.id,
            'prompt': prompt, 'result': result, 'success': success, 'error': error or False,
        })

    def _run_action_ai_agent_multi(self, eval_context=None):
        # ponytail: synchronous — correct for step chaining and manual runs. On a
        # heavy on_create/on_write trigger it blocks that save; prefer scheduled
        # or manual triggers, or a queued wrapper, for those.
        self.ensure_one()
        records = (eval_context or {}).get('records') or (eval_context or {}).get('record')
        if not records:
            return False
        bot = self.env['mail.bot']
        for record in records:
            prompt = self._ai_render_prompt(record)
            try:
                result = bot._run_agent(prompt, use_tools=self.ai_use_tools)
                success, error = True, False
            except Exception as e:
                result, success, error = '', False, str(e)[:500]
                _logger.exception("Bước AI %s lỗi trên %s#%s", self.id, record._name, record.id)
            if success and self.ai_result_field_id:
                try:
                    record.sudo().write({self.ai_result_field_id.name: result})
                except Exception as e:
                    success, error = False, ("Ghi trường thất bại: %s" % e)[:500]
            self._log(record, prompt, result, success, error)
        return False

    def _run_action_ai_condition_multi(self, eval_context=None):
        """Evaluate a condition per record and run the then/else branch — routing,
        the way n8n's IF node does."""
        self.ensure_one()
        records = (eval_context or {}).get('records') or (eval_context or {}).get('record')
        if not records:
            return False
        for record in records:
            try:
                matched = bool(safe_eval(
                    self.condition_expr or 'False',
                    {'record': record, 'env': self.env}))
                branch = self.then_action_id if matched else self.else_action_id
                if branch:
                    branch.with_context(
                        active_model=record._name, active_id=record.id,
                        active_ids=record.ids).run()
                self._log(record, self.condition_expr,
                          _('%(kq)s → %(nhanh)s', kq='ĐÚNG' if matched else 'SAI',
                            nhanh=branch.name if branch else _('(không có nhánh)')), True)
            except Exception as e:
                _logger.exception("Node điều kiện %s lỗi trên %s#%s", self.id, record._name, record.id)
                self._log(record, self.condition_expr, '', False, str(e)[:500])
        return False

    def _http_call(self, method, url, **kwargs):
        """Single HTTP round-trip. Isolated so tests can mock it."""
        with httpx.Client(follow_redirects=True) as client:
            return client.request(method.upper(), url, **kwargs)

    def _run_action_ai_http_multi(self, eval_context=None):
        """Call an external API and store the response, so a later step can use
        it — n8n's HTTP Request node. Stronger than webhook (which only fires)."""
        self.ensure_one()
        records = (eval_context or {}).get('records') or (eval_context or {}).get('record')
        if not records:
            return False
        try:
            headers = json.loads(self.http_headers) if self.http_headers else {}
        except Exception:
            headers = {}
        method = self.http_method or 'get'
        for record in records:
            url = self._ai_substitute(self.http_url or '', record)
            body = self._ai_substitute(self.http_body or '', record)
            kwargs = {'headers': headers, 'timeout': self.http_timeout or 30}
            if method in ('post', 'put', 'patch') and body:
                try:
                    kwargs['json'] = json.loads(body)
                except Exception:
                    kwargs['content'] = body
            try:
                resp = self._http_call(method, url, **kwargs)
                text = (resp.text or '')[:20000]
                ok = resp.status_code < 400
                if ok and self.http_result_field_id:
                    record.sudo().write({self.http_result_field_id.name: text})
                self._log(record, '%s %s' % (method.upper(), url),
                          'HTTP %s\n%s' % (resp.status_code, text[:2000]),
                          ok, False if ok else 'HTTP %s' % resp.status_code)
            except Exception as e:
                _logger.exception("Node HTTP %s lỗi trên %s#%s", self.id, record._name, record.id)
                self._log(record, '%s %s' % (method.upper(), url), '', False, str(e)[:500])
        return False
