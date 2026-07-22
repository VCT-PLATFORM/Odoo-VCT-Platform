# Written for VCT Platform. Not part of Odoo S.A.
import json
import logging
import time

import httpx

from markupsafe import Markup
from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.mail import html2plaintext
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Network-related exception types for retry logic
_NETWORK_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, OSError)

# call_button_method may only fire genuine business actions. A bare getattr()
# call by name is an arbitrary-code primitive: `unlink` alone lets a prompt
# injection wipe the ledger. Allow only these prefixes, never a private method.
SAFE_METHOD_PREFIXES = ('action_', 'button_', 'toggle_')
# defence in depth: even if a model ever names a destructive method with an
# allowed prefix, keep the classics hard-blocked.
BLOCKED_METHODS = frozenset({
    'unlink', 'write', 'create', 'copy', 'browse', 'search', 'search_read',
    'read', 'load', 'import_file', 'export_data', '_unlink', 'fields_get',
})

MAX_ITERATIONS = 10


class MailBot(models.AbstractModel):
    _inherit = 'mail.bot'

    def _register_hook(self):
        odoobot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if odoobot and odoobot.name != 'Trợ lý AI':
            odoobot.sudo().write({
                'name': 'Trợ lý AI',
                'email': 'assistant.ai@vctplatform.com',
            })
        return super()._register_hook()

    def _sanitize_record_values(self, env, model_name, values):
        if not isinstance(values, dict):
            return {}
        cleaned = {}
        for k, v in values.items():
            if isinstance(v, str):
                # Convert ISO '2026-07-21T16:00:00' to Odoo format '2026-07-21 16:00:00'
                if 'T' in v and len(v) >= 16 and v[:4].isdigit():
                    v = v.replace('T', ' ').split('+')[0].split('Z')[0].strip()
                    if len(v) == 16:
                        v += ':00'
                cleaned[k] = v
            else:
                cleaned[k] = v

        # Automatically assign tasks to the chatting user so they appear in their Todos
        if model_name == 'project.task':
            if 'user_ids' not in cleaned and 'user_id' not in cleaned:
                cleaned['user_ids'] = [(6, 0, [env.uid])]
            elif 'user_ids' in cleaned and isinstance(cleaned['user_ids'], list):
                first = cleaned['user_ids'][0] if cleaned['user_ids'] else None
                if isinstance(first, int):
                    cleaned['user_ids'] = [(6, 0, cleaned['user_ids'])]

        return cleaned

    # ------------------------------------------------------------------
    # Tool execution — runs with the chatting user's ACLs (see _cron_process_jobs)
    # ------------------------------------------------------------------
    def _execute_agent_tool(self, env, tool_name, arguments):
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(args, dict):
                args = {}

            if tool_name == 'list_models':
                search_term = args.get('search')
                domain = []
                if search_term:
                    domain = ['|', ('model', 'ilike', search_term), ('name', 'ilike', search_term)]
                records = env['ir.model'].search(domain, limit=100)
                return json.dumps(
                    [{'model': m.model, 'name': m.name, 'transient': m.transient} for m in records],
                    ensure_ascii=False)

            if tool_name == 'get_model_fields':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist in Odoo."
                fields_info = env[model_name].fields_get()
                return json.dumps({
                    name: {
                        'type': info.get('type'),
                        'string': info.get('string'),
                        'required': info.get('required', False),
                        'relation': info.get('relation'),
                    }
                    for name, info in fields_info.items()
                }, ensure_ascii=False)

            if tool_name == 'search_read_records':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist."
                domain = self._parse_domain(args.get('domain'))
                if isinstance(domain, str):        # parse error, surface it
                    return domain
                records = env[model_name].search(domain, limit=args.get('limit') or 80)
                return json.dumps(records.read(args.get('fields') or []),
                                  default=str, ensure_ascii=False)

            if tool_name == 'read_group':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist."
                domain = self._parse_domain(args.get('domain'))
                if isinstance(domain, str):
                    return domain
                groupby = args.get('groupby') or []
                aggregates = args.get('aggregates') or ['__count']
                result = env[model_name].formatted_read_group(
                    domain, groupby=groupby, aggregates=aggregates)
                return json.dumps(result, default=str, ensure_ascii=False)

            if tool_name == 'find_menu':
                term = args.get('search') or ''
                # complete_name is a non-stored recursive compute -> not
                # searchable; search the real 'name' field, show the full path
                menus = env['ir.ui.menu'].search(
                    [('name', 'ilike', term)], limit=40)
                return json.dumps([
                    {'menu': m.complete_name,
                     'action': m.action.display_name if m.action else None}
                    for m in menus
                ], ensure_ascii=False)

            if tool_name == 'get_record_url':
                model_name = args.get('model')
                rec_id = args.get('id')
                if not model_name or not rec_id:
                    return "Error: cần 'model' và 'id'."
                return f"/web#id={int(rec_id)}&model={model_name}&view_type=form"

            if tool_name == 'create_record':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist."
                vals = self._sanitize_record_values(env, model_name, args.get('values') or {})
                record = env[model_name].create(vals)
                _logger.info("AI Agent (uid=%s) created %s#%s with vals %s", env.uid, model_name, record.id, vals)
                return json.dumps({
                    'id': record.id,
                    'status': 'success',
                    'name': record.display_name,
                    'url': f"/web#id={record.id}&model={model_name}&view_type=form"
                }, ensure_ascii=False)

            if tool_name == 'write_record':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist."
                ids = args.get('ids') or []
                vals = self._sanitize_record_values(env, model_name, args.get('values') or {})
                env[model_name].browse(ids).write(vals)
                _logger.info("AI Agent (uid=%s) wrote %s%s with vals %s", env.uid, model_name, ids, vals)
                return json.dumps({'status': 'success', 'updated_ids': ids}, ensure_ascii=False)

            if tool_name == 'delete_record':
                model_name = args.get('model')
                if model_name not in env:
                    return f"Error: Model '{model_name}' does not exist."
                ids = args.get('ids') or []
                # Safety: only allow deleting records from safe models
                SAFE_DELETE_MODELS = {
                    'project.task', 'calendar.event', 'note.note',
                    'crm.lead', 'mail.activity',
                }
                if model_name not in SAFE_DELETE_MODELS:
                    return (f"Error: Xóa bản ghi trong model '{model_name}' không được phép. "
                            f"Chỉ cho phép xóa: {', '.join(sorted(SAFE_DELETE_MODELS))}.")
                env[model_name].browse(ids).unlink()
                _logger.info("AI Agent (uid=%s) deleted %s%s", env.uid, model_name, ids)
                return json.dumps({'status': 'success', 'deleted_ids': ids}, ensure_ascii=False)

            if tool_name == 'call_button_method':
                return self._call_button_method(env, args)

            return f"Error: Tool '{tool_name}' is not recognized."
        except Exception as e:
            _logger.exception("Error executing agent tool %s", tool_name)
            return f"Exception raised during tool execution: {e}"

    def _parse_domain(self, domain_str):
        """Return a domain list, or an error string if it cannot be parsed.

        A silent fall-back to [] would make one malformed filter read (or later
        write) the entire table — exactly the surprise to avoid."""
        if not domain_str:
            return []
        if isinstance(domain_str, list):
            return domain_str
        try:
            return json.loads(domain_str)
        except Exception:
            pass
        try:
            return safe_eval(domain_str)
        except Exception:
            return (f"Error: domain không hợp lệ: {domain_str!r}. "
                    "Dùng JSON, ví dụ [[\"state\",\"=\",\"posted\"]].")

    def _call_button_method(self, env, args):
        model_name = args.get('model')
        method = args.get('method') or ''
        ids = args.get('ids') or []
        if model_name not in env:
            return f"Error: Model '{model_name}' does not exist."
        if (method in BLOCKED_METHODS or method.startswith('_')
                or not method.startswith(SAFE_METHOD_PREFIXES)):
            return (f"Error: phương thức '{method}' bị chặn vì lý do an toàn. "
                    "Chỉ cho phép các phương thức action_/button_/toggle_ "
                    "(không bao giờ xoá dữ liệu).")
        records = env[model_name].browse(ids)
        if not hasattr(records, method):
            return f"Error: Method '{method}' does not exist on model '{model_name}'."
        res = getattr(records, method)()
        _logger.info("AI Agent (uid=%s) called %s.%s%s", env.uid, model_name, method, ids)
        return json.dumps({'status': 'success', 'result': str(res)}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Enqueue: never run the agent loop inside the message-posting txn
    # ------------------------------------------------------------------
    def _apply_logic(self, channel, values, command=None):
        channel.ensure_one()
        odoobot = self.env.ref("base.partner_root")

        if values.get("author_id") == odoobot.id or (
                values.get("message_type") != "comment" and not command):
            return

        is_dm = channel.channel_type == "chat" and odoobot in channel.channel_member_ids.partner_id
        is_mentioned = odoobot.id in (values.get("partner_ids") or [])
        if not (is_dm or is_mentioned):
            return super()._apply_logic(channel, values, command=command)

        # hand off to a background job so a multi-minute agent loop never holds
        # the HTTP worker or the posting transaction open
        self.env['vct.llm.job'].sudo().create({
            'channel_id': channel.id,
            'user_id': self.env.uid,
        })._trigger_cron()

        bot_member = channel.channel_member_ids.filtered(lambda m: m.partner_id == odoobot)
        if bot_member:
            bot_member._notify_typing(True)

    # ------------------------------------------------------------------
    # The agent loop — runs in the cron, as the chatting user
    # ------------------------------------------------------------------
    def _llm_call(self, api_url, headers, payload):
        """Single HTTP round-trip with 3-retry exponential backoff for network errors."""
        last_err = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=300) as client:
                    response = client.post(api_url, json=payload, headers=headers)
                    if response.status_code >= 400:
                        raise Exception(response.text)
                    return response.json()
            except _NETWORK_ERRORS as e:
                last_err = e
                if attempt < 2:
                    wait = 2 ** attempt  # 1s, 2s
                    _logger.warning(
                        "LLM network error (attempt %d/3): %s — retrying in %ds",
                        attempt + 1, e, wait
                    )
                    time.sleep(wait)
                else:
                    _logger.error("LLM network error after 3 attempts: %s", e)
            except Exception:
                raise
        raise last_err

    def _run_agent(self, user_text, system_prompt=None, use_tools=True):
        """One-shot agent turn reusable outside Discuss (e.g. AI workflow steps).
        Runs with the current env's ACLs and returns the text reply. Raises if no
        API key is configured, so callers can log the failure."""
        cfg = self._agent_config()
        is_local_or_ollama = any(k in cfg['api_url'].lower() for k in ('11434', 'ollama', 'localhost', '127.0.0.1'))
        if not cfg['api_key'] and not is_local_or_ollama:
            raise UserError(_("Chưa cấu hình LLM API Key (Cài đặt → AI Assistant)."))
        if system_prompt:
            cfg = dict(cfg, system_prompt=system_prompt)
        tools = self._tool_schema() if use_tools else []
        messages = [{'role': 'user', 'content': user_text}]
        if 'anthropic' in cfg['api_url'].lower():
            return self._run_anthropic(cfg, tools, messages)
        return self._run_openai(cfg, tools, messages)

    def _agent_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'mode': ICP.get_param('vct_llm.mode', 'auto_hybrid'),
            'api_url': (ICP.get_param('vct_llm.api_url')
                        or 'http://192.168.12.44:11434/v1/chat/completions').strip(),
            'api_key': ICP.get_param('vct_llm.api_key', ''),
            'model': ICP.get_param('vct_llm.model_name') or 'qwen3-fast:latest',
            'cloud_url': (ICP.get_param('vct_llm.cloud_url')
                          or 'https://api.openai.com/v1/chat/completions').strip(),
            'cloud_key': ICP.get_param('vct_llm.cloud_key', ''),
            'cloud_model': ICP.get_param('vct_llm.cloud_model') or 'gpt-4o-mini',
            'system_prompt': ICP.get_param('vct_llm.system_prompt') or (
                "Bạn là Trợ lý AI cao cấp của VCT Platform, tích hợp sâu trong Odoo ERP.\n\n"
                "## KHẢ NĂNG HÀNH ĐỘNG TRỰC TIẾP TRÊN HỆ THỐNG\n"
                "Bạn CÓ THỂ và NÊN chủ động dùng các công cụ để TỰ ĐỘNG thực hiện ngay khi người dùng yêu cầu:\n"
                "- **Tạo Việc cần làm (Todo)**: Khi người dùng nói 'thêm việc', 'tạo todo', 'nhắc tôi', 'đặt việc' → dùng `create_record` với model=`project.task`.\n"
                "  Ví dụ: 'Họp triển khai AI lúc 17h hôm nay' → tạo task với name='Họp triển khai AI', date_deadline=<ngày hôm nay> 17:00:00\n"
                "- **Tạo Lịch hẹn**: Khi người dùng nói 'đặt lịch', 'tạo cuộc hẹn', 'lên lịch' → dùng `create_record` với model=`calendar.event`.\n"
                "- **Xóa bản ghi**: Khi người dùng nói 'xóa việc', 'hủy task' → tìm bản ghi rồi dùng `delete_record`.\n"
                "- **Tra cứu dữ liệu**: Dùng `search_read_records` để lấy danh sách việc cần làm, đơn hàng, hóa đơn, v.v.\n"
                "- **Cập nhật bản ghi**: Dùng `write_record` để sửa nội dung bản ghi hiện có.\n\n"
                "## NGÀY GIỜ\n"
                "Ngày giờ hiện tại sẽ được cung cấp ở đầu mỗi tin nhắn hệ thống. Dùng nó để tính toán 'hôm nay', 'ngày mai', 'tuần này', v.v.\n"
                "Định dạng datetime khi tạo bản ghi: YYYY-MM-DD HH:MM:SS (UTC+7, ví dụ: 2025-01-15 17:00:00)\n\n"
                "## MODEL ODOO QUAN TRỌNG\n"
                "- `project.task`: Việc cần làm / Task. Fields: name, date_deadline (datetime), description (html), user_ids (many2many uid), project_id (bỏ trống = personal todo).\n"
                "- `calendar.event`: Lịch hẹn / Cuộc họp. Fields: name, start (datetime), stop (datetime), description, partner_ids.\n"
                "- `sale.order`: Đơn bán hàng. Fields: name, state, amount_total, partner_id.\n"
                "- `account.move`: Hóa đơn kế toán. Fields: name, move_type, state, amount_total.\n"
                "- `res.partner`: Khách hàng/Nhà cung cấp. Fields: name, email, phone.\n\n"
                "## QUY TẮC TRÌNH BÀY\n"
                "1. **BÁO CÁO & BẢNG SỐ LIỆU**: Dùng BẢNG MARKDOWN chuẩn (`| Chỉ tiêu | Số tiền | Ghi chú |`).\n"
                "2. **CẤU TRÚC**: Phân chia phần bằng Tiêu đề (`##`, `###`) và đường phân cách (`---`).\n"
                "3. **PHẢN HỒI HÀNH ĐỘNG**: Sau khi tạo/sửa/xóa bản ghi, luôn xác nhận ✅ rõ ràng với link đến bản ghi.\n"
                "4. **HOÀN THÀNH TRỌN VẸN**: Tuyệt đối KHÔNG cắt ngang hay bỏ dở giữa chừng."
            ),
        }

    def _tool_schema(self):
        return [
            {"type": "function", "function": {
                "name": "search_read_records",
                "description": (
                    "Tìm và đọc danh sách bản ghi theo bộ lọc domain. "
                    "Dùng để tra cứu Việc cần làm (model=project.task), Hóa đơn (model=account.move), "
                    "Đơn hàng (model=sale.order), Khách hàng (model=res.partner), "
                    "Lịch hẹn (model=calendar.event), v.v."
                ),
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string", "description": "Tên model Odoo, vd: project.task, sale.order, account.move"},
                    "domain": {"type": "string", "description": "Domain JSON, vd [[\"state\",\"=\",\"posted\"]]. Để trống để lấy tất cả."},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Danh sách trường cần lấy, vd [\"name\",\"date_deadline\",\"user_ids\"]"},
                    "limit": {"type": "integer", "description": "Giới hạn số bản ghi, mặc định 80"}},
                    "required": ["model"]}}},
            {"type": "function", "function": {
                "name": "read_group",
                "description": "Tổng hợp số liệu (tổng/đếm/trung bình) gom theo nhóm. Dùng cho báo cáo tổng hợp.",
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string"},
                    "domain": {"type": "string", "description": "Domain JSON"},
                    "groupby": {"type": "array", "items": {"type": "string"},
                                "description": "Các trường gom nhóm, vd [\"partner_id\", \"state\"]"},
                    "aggregates": {"type": "array", "items": {"type": "string"},
                                   "description": "vd [\"amount_total:sum\",\"__count\"]"}},
                    "required": ["model"]}}},
            {"type": "function", "function": {
                "name": "find_menu",
                "description": "Tìm menu trong Odoo để hướng dẫn người dùng điều hướng.",
                "parameters": {"type": "object", "properties": {
                    "search": {"type": "string"}}, "required": ["search"]}}},
            {"type": "function", "function": {
                "name": "get_record_url",
                "description": "Lấy đường dẫn URL tới form một bản ghi cụ thể để chèn link trực tiếp cho người dùng click vào.",
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string"}, "id": {"type": "integer"}},
                    "required": ["model", "id"]}}},
            {"type": "function", "function": {
                "name": "create_record",
                "description": (
                    "Tạo mới một bản ghi trong Odoo. "
                    "Ví dụ thường dùng:\n"
                    "- Tạo Việc cần làm (Todo): model=project.task, values={\"name\": \"Tên việc\", \"date_deadline\": \"2025-01-15 17:00:00\"}\n"
                    "- Tạo Lịch hẹn: model=calendar.event, values={\"name\": \"Tên cuộc họp\", \"start\": \"2025-01-15 09:00:00\", \"stop\": \"2025-01-15 10:00:00\"}\n"
                    "- Tạo Liên hệ: model=res.partner, values={\"name\": \"Tên\", \"email\": \"email@example.com\"}\n"
                    "QUAN TRỌNG: Dùng datetime dạng YYYY-MM-DD HH:MM:SS (có dấu cách giữa ngày và giờ)."
                ),
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string", "description": "Tên model Odoo, vd: project.task, calendar.event"},
                    "values": {"type": "object", "description": "Dict các giá trị trường cần thiết lập"}},
                    "required": ["model", "values"]}}},
            {"type": "function", "function": {
                "name": "write_record",
                "description": "Cập nhật (sửa) bản ghi hiện có. Dùng khi người dùng muốn sửa tên, ngày, trạng thái của một bản ghi.",
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "integer"}, "description": "Danh sách ID bản ghi cần cập nhật"},
                    "values": {"type": "object", "description": "Dict các giá trị cần cập nhật"}},
                    "required": ["model", "ids", "values"]}}},
            {"type": "function", "function": {
                "name": "delete_record",
                "description": (
                    "Xóa bản ghi. Chỉ áp dụng cho các model an toàn: project.task, calendar.event, note.note, crm.lead, mail.activity. "
                    "Trước khi xóa, hãy tìm bản ghi bằng search_read_records để lấy ID chính xác."
                ),
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string", "description": "Model cần xóa (chỉ: project.task, calendar.event, note.note, crm.lead, mail.activity)"},
                    "ids": {"type": "array", "items": {"type": "integer"}, "description": "Danh sách ID bản ghi cần xóa"}},
                    "required": ["model", "ids"]}}},
            {"type": "function", "function": {
                "name": "call_button_method",
                "description": "Chạy phương thức nghiệp vụ action_/button_/toggle_ của bản ghi (xác nhận đơn hàng, xác nhận hóa đơn, v.v.). Không cho phép xóa dữ liệu.",
                "parameters": {"type": "object", "properties": {
                    "model": {"type": "string"}, "method": {"type": "string",
                    "description": "Tên phương thức, vd: action_confirm, button_validate, action_post"},
                    "ids": {"type": "array", "items": {"type": "integer"}}},
                    "required": ["model", "method", "ids"]}}},
        ]

    def _channel_history(self, channel, odoobot):
        history = self.env['mail.message'].sudo().search([
            ('res_id', '=', channel.id),
            ('model', '=', 'discuss.channel'),
            ('message_type', '=', 'comment'),
        ], limit=10, order='id desc')
        raw = []
        for msg in reversed(history):
            role = "assistant" if msg.author_id == odoobot else "user"
            text = html2plaintext(msg.body or '').strip()
            if text:
                raw.append({"role": role, "content": text})
        merged = []
        for msg in raw:
            if merged and merged[-1]['role'] == msg['role']:
                merged[-1]['content'] += "\n" + msg['content']
            else:
                merged.append(msg)
        return merged

    def _is_complex_task(self, user_text, messages):
        text = (user_text or '').lower()
        complex_keywords = [
            'báo cáo tài chính', 'bảng cân đối', 'báo cáo kết quả', 'lợi nhuận',
            'thông tư 99', 'phân tích', 'tổng hợp báo cáo', 'lập kế hoạch',
            'so sánh doanh thu', 'doanh thu theo', 'phân tích tài chính',
            'nghiệp vụ kế toán', 'tùy biến module', 'code python', 'thuế'
        ]
        if any(kw in text for kw in complex_keywords):
            return True
        if len(text) > 1000:
            return True
        total_len = sum(len(m.get('content', '')) for m in messages if isinstance(m.get('content'), str))
        if total_len > 2500:
            return True
        return False

    def _is_ollama_native(self, url):
        """Detect if URL points to an Ollama server (use native /api/chat)."""
        lower = url.lower()
        return any(k in lower for k in ('11434', '/api/chat', '/api/generate'))

    def _dispatch_llm_call(self, cfg, tools, messages, use_cloud=False):
        active_cfg = dict(cfg)
        if use_cloud and cfg.get('cloud_key'):
            active_cfg['api_url'] = cfg['cloud_url']
            active_cfg['api_key'] = cfg['cloud_key']
            active_cfg['model'] = cfg['cloud_model']

        url = active_cfg['api_url'].lower()
        if 'anthropic' in url:
            return self._run_anthropic(active_cfg, tools, messages)
        if self._is_ollama_native(active_cfg['api_url']):
            # Build native Ollama endpoint if needed
            base = active_cfg['api_url'].split('/v1')[0].split('/api')[0].rstrip('/')
            active_cfg = dict(active_cfg, api_url=base + '/api/chat')
            return self._run_ollama(active_cfg, tools, messages)
        return self._run_openai(active_cfg, tools, messages)

    def _format_reply_html(self, text):
        if not text:
            return ""

        import markdown

        # Render full Markdown with tables, code blocks, lists, nl2br
        try:
            html_content = markdown.markdown(
                text,
                extensions=['tables', 'fenced_code', 'sane_lists', 'nl2br']
            )
        except Exception as e:
            _logger.warning("Markdown parsing failed: %s", e)
            html_content = f"<p>{text}</p>"

        # Style table elements with Bootstrap classes & custom CSS
        html_content = html_content.replace(
            '<table>',
            '<table class="table table-sm table-bordered table-striped o_ai_response_table">'
        )
        html_content = html_content.replace(
            '<thead>',
            '<thead class="table-dark">'
        )

        return f'<div class="o_ai_response_content">{html_content}</div>'

    def _process_channel(self, channel):
        """Run the full agent loop for a channel and post the reply.
        `self.env` here already carries the chatting user's ACLs."""
        odoobot = self.env.ref("base.partner_root")
        bot_member = channel.channel_member_ids.filtered(lambda m: m.partner_id == odoobot)
        if bot_member:
            bot_member._notify_typing(True)

        from datetime import datetime
        import pytz

        cfg = self._agent_config()
        tools = self._tool_schema()
        messages = self._channel_history(channel, odoobot)

        # Inject current datetime context so AI knows "today", "17h hôm nay", etc.
        try:
            tz = pytz.timezone('Asia/Ho_Chi_Minh')
            now_local = datetime.now(tz)
            dt_context = (
                f"[HỆ THỐNG] Ngày giờ hiện tại: {now_local.strftime('%A, %d/%m/%Y %H:%M')} (GMT+7). "
                f"Ngày hôm nay: {now_local.strftime('%Y-%m-%d')}. "
                f"Giờ hiện tại: {now_local.strftime('%H:%M')}."
            )
            # Prepend datetime context to the latest user message
            if messages and messages[-1].get('role') == 'user':
                messages[-1]['content'] = dt_context + "\n" + messages[-1]['content']
            elif messages:
                messages.append({'role': 'user', 'content': dt_context})
        except Exception:
            pass

        user_text = ""
        for m in reversed(messages):
            if m.get('role') == 'user' and isinstance(m.get('content'), str):
                user_text = m['content']
                break

        use_cloud = False
        if cfg['mode'] == 'auto_hybrid' and cfg['cloud_key']:
            if self._is_complex_task(user_text, messages):
                use_cloud = True

        reply_text = ""
        try:
            if use_cloud:
                _logger.info("AI Auto-Routing: Using Cloud AI (%s) for complex task", cfg['cloud_model'])
            else:
                _logger.info("AI Auto-Routing: Using Local LLM (%s) for normal task", cfg['model'])
            reply_text = self._dispatch_llm_call(cfg, tools, messages, use_cloud=use_cloud)
        except Exception as primary_err:
            _logger.warning("Primary LLM call failed (%s). Attempting Fallback...", primary_err)
            try:
                # Fallback mechanism: if Cloud failed, try Local; if Local failed, try Cloud (if available)
                if use_cloud:
                    _logger.info("Fallback: Switching to Local LLM (%s)", cfg['model'])
                    reply_text = self._dispatch_llm_call(cfg, tools, messages, use_cloud=False)
                elif cfg['cloud_key']:
                    _logger.info("Fallback: Switching to Cloud AI (%s)", cfg['cloud_model'])
                    reply_text = self._dispatch_llm_call(cfg, tools, messages, use_cloud=True)
                else:
                    raise primary_err
            except Exception as fallback_err:
                _logger.exception("Both Primary and Fallback LLMs failed")
                err_str = str(fallback_err)
                if any(kw in err_str for kw in ('Errno', 'route', 'connect', 'timeout', 'timed out', 'Network')):
                    reply_text = (
                        "⚠️ **Không thể kết nối đến máy chủ AI lúc này.**\n\n"
                        "Có thể do:\n"
                        "- Mạng nội bộ bị gián đoạn tạm thời\n"
                        "- Máy chủ Ollama đang khởi động lại\n\n"
                        "💡 **Bạn hãy thử lại sau vài giây.** Nếu lỗi tiếp tục, vui lòng kiểm tra kết nối mạng hoặc liên hệ quản trị viên."
                    )
                else:
                    reply_text = (
                        f"⚠️ **Trợ lý AI gặp lỗi không mong muốn.**\n\n"
                        f"Chi tiết: `{err_str}`\n\n"
                        "💡 Vui lòng thử lại hoặc liên hệ quản trị viên nếu lỗi tiếp tục."
                    )
        finally:
            if bot_member:
                bot_member._notify_typing(False)

        body_html = self._format_reply_html(reply_text or _("Đã hoàn thành, không có nội dung trả lời thêm."))
        channel.sudo().message_post(
            author_id=odoobot.id, message_type="comment", subtype_xmlid="mail.mt_comment",
            body=Markup(body_html))

    def _run_anthropic(self, cfg, openai_tools, messages):
        tools = [{"name": t['function']['name'],
                  "description": t['function']['description'],
                  "input_schema": t['function']['parameters']} for t in openai_tools]
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        headers = {"Content-Type": "application/json", "x-api-key": cfg['api_key'] or "",
                   "anthropic-version": "2023-06-01"}
        for _i in range(MAX_ITERATIONS):
            payload = {"model": cfg['model'], "system": cfg['system_prompt'],
                       "messages": messages, "max_tokens": 65536}
            if tools:
                payload["tools"] = tools
            data = self._llm_call(cfg['api_url'], headers, payload)
            blocks = data.get('content', [])
            messages.append({"role": "assistant", "content": blocks})
            tool_uses = [b for b in blocks if b.get('type') == 'tool_use']
            if not tool_uses:
                return "".join(b.get('text', '') for b in blocks if b.get('type') == 'text')
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b['id'],
                 "content": self._execute_agent_tool(self.env, b['name'], b['input'])}
                for b in tool_uses]})
        return _("Đã đạt giới hạn số bước xử lý.")

    def _run_openai(self, cfg, tools, messages):
        headers = {"Content-Type": "application/json"}
        if cfg['api_key']:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        api_messages = [{"role": "system", "content": cfg['system_prompt']}] + messages
        for _i in range(MAX_ITERATIONS):
            payload = {
                "model": cfg['model'],
                "messages": api_messages,
                "temperature": 0.3,
                "max_tokens": 65536,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            data = self._llm_call(cfg['api_url'], headers, payload)
            message = data['choices'][0]['message']
            assistant_msg = {"role": "assistant"}
            if message.get("content"):
                assistant_msg["content"] = message["content"]
            if message.get("tool_calls"):
                assistant_msg["tool_calls"] = message["tool_calls"]
            api_messages.append(assistant_msg)
            tool_calls = message.get('tool_calls')
            if not tool_calls:
                return message.get('content') or ''
            for call in tool_calls:
                api_messages.append({
                    "role": "tool", "tool_call_id": call['id'],
                    "name": call['function']['name'],
                    "content": self._execute_agent_tool(
                        self.env, call['function']['name'], call['function']['arguments'])})
        return _("Đã đạt giới hạn số bước xử lý.")

    def _run_ollama(self, cfg, tools, messages):
        """Native Ollama /api/chat endpoint — avoids OpenAI-compat timeout & stringified tool_call errors."""
        headers = {"Content-Type": "application/json"}
        api_messages = [{"role": "system", "content": cfg['system_prompt']}] + messages
        for _i in range(MAX_ITERATIONS):
            payload = {
                "model": cfg['model'],
                "messages": api_messages,
                "stream": False,
                "options": {"num_predict": 65536, "num_ctx": 65536, "temperature": 0.3},
            }
            if tools:
                payload["tools"] = tools
            data = self._llm_call(cfg['api_url'], headers, payload)
            msg = data.get('message', {})
            content = msg.get('content', '')
            tool_calls_raw = msg.get('tool_calls', [])

            # Preserve native Ollama message structure in message history
            api_messages.append(msg)

            if not tool_calls_raw:
                return content

            for tc in tool_calls_raw:
                fn = tc.get('function', {})
                fn_name = fn.get('name', '')
                fn_args = fn.get('arguments', {})
                result = self._execute_agent_tool(self.env, fn_name, fn_args)
                api_messages.append({
                    "role": "tool",
                    "content": str(result),
                })
        return _("Đã đạt giới hạn số bước xử lý.")
