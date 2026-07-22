# -*- coding: utf-8 -*-
import json
import logging
import httpx
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vct_llm_mode = fields.Selection(
        selection=[
            ('single', 'Cố định 1 Mô hình (Single Model)'),
            ('auto_hybrid', 'Tự động chọn Mô hình (Hybrid: Local + Cloud AI)'),
        ],
        string='Chế độ hoạt động (Routing Mode)',
        config_parameter='vct_llm.mode',
        default='auto_hybrid',
        help='Tự động dùng Local LLM cho tác vụ thông thường và Cloud AI cho báo cáo/tác vụ phức tạp'
    )

    vct_llm_api_url = fields.Char(
        string='LLM API URL (Local/Primary)',
        config_parameter='vct_llm.api_url',
        default='http://192.168.12.44:11434/v1/chat/completions',
        help='The HTTP endpoint for Odoo to post chat requests'
    )
    vct_llm_api_key = fields.Char(
        string='LLM API Key (Local/Primary)',
        config_parameter='vct_llm.api_key',
        help='Authorization bearer token or API key'
    )
    vct_llm_model_name = fields.Char(
        string='LLM Model Name (Local/Primary)',
        config_parameter='vct_llm.model_name',
        default='qwen3-fast:latest',
        help='Model identifier currently in use'
    )

    # Cloud AI Provider fields for Auto-Hybrid Routing & Fallback
    vct_llm_cloud_url = fields.Char(
        string='Cloud LLM API URL',
        config_parameter='vct_llm.cloud_url',
        default='https://api.openai.com/v1/chat/completions',
        help='Cloud AI endpoint (OpenAI, DeepSeek, Anthropic, etc.)'
    )
    vct_llm_cloud_key = fields.Char(
        string='Cloud LLM API Key',
        config_parameter='vct_llm.cloud_key',
        help='API Key for Cloud AI provider'
    )
    vct_llm_cloud_model = fields.Char(
        string='Cloud LLM Model Name',
        config_parameter='vct_llm.cloud_model',
        default='gpt-4o-mini',
        help='Model name for Cloud AI (e.g., gpt-4o-mini, deepseek-chat, claude-3-5-sonnet)'
    )

    vct_llm_system_prompt = fields.Char(
        string='System Prompt',
        config_parameter='vct_llm.system_prompt',
        default=(
            "Bạn là Trợ lý AI chuyên nghiệp của VCT Platform tích hợp trong Odoo. "
            "QUY TẮC TRÌNH BÀY BẮT BUỘC: 1. Luôn trình bày TRỰC QUAN, CHỦ ĐỘNG XUỐNG DÒNG rõ ràng giữa các ý. "
            "2. Khi liệt kê danh sách hoặc ví dụ, BẮT BUỘC xuống dòng riêng cho từng mục, sử dụng gạch đầu dòng (-) hoặc đánh số (1., 2., 3.). "
            "3. KHÔNG BAO GIỜ gộp nhiều tiêu chí hoặc ví dụ thành 1 đoạn văn dài liền khối. "
            "4. Sử dụng in đậm **từ khoá chính**."
        ),
        help='Primary instructions for the AI bot behavior'
    )

    # Dynamic selection of fetched models
    vct_llm_model_selection = fields.Selection(
        selection='_get_fetched_models',
        string='Detected Models',
        help='Select from the list of models retrieved from the API'
    )

    def _get_fetched_models(self):
        ICP = self.env['ir.config_parameter'].sudo()
        models_json = ICP.get_param('vct_llm.available_models', '[]')
        try:
            model_list = json.loads(models_json)
        except Exception:
            model_list = []
        
        # Sort and return
        if model_list and isinstance(model_list, list):
            return [(m, m) for m in model_list]
        return [
            ('qwen3-fast:latest', 'qwen3-fast:latest (Local Server 192.168.12.44)'),
            ('qwen3:14b', 'qwen3:14b (Local Server 192.168.12.44)'),
            ('gpt-4o-mini', 'gpt-4o-mini (Cloud OpenAI)'),
            ('gpt-4o', 'gpt-4o (Cloud OpenAI)'),
            ('deepseek-chat', 'deepseek-chat (Cloud DeepSeek)'),
            ('claude-3-5-sonnet', 'claude-3-5-sonnet (Cloud Anthropic)')
        ]

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            vct_llm_model_selection=ICP.get_param('vct_llm.model_name', 'qwen3-fast:latest')
        )
        return res

    def set_values(self):
        super().set_values()
        if self.vct_llm_model_selection:
            self.env['ir.config_parameter'].sudo().set_param('vct_llm.model_name', self.vct_llm_model_selection)

    @api.onchange('vct_llm_model_selection')
    def _onchange_vct_llm_model_selection(self):
        if self.vct_llm_model_selection:
            self.vct_llm_model_name = self.vct_llm_model_selection

    def action_fetch_models(self):
        self.ensure_one()
        url = (self.vct_llm_api_url or '').strip() or 'http://192.168.12.44:11434/v1/chat/completions'
        is_local_or_ollama = any(k in url.lower() for k in ('11434', 'ollama', 'localhost', '127.0.0.1', '192.168.', '10.', '172.16.'))

        if not self.vct_llm_api_key and not is_local_or_ollama:
            raise UserError("Please fill in the LLM API Key first.")

        # Build candidate URLs for model endpoint discovery
        candidates = []
        is_anthropic = 'anthropic' in url.lower()

        if is_anthropic:
            candidates.append('https://api.anthropic.com/v1/models')
        else:
            if '/chat/completions' in url:
                candidates.append(url.replace('/chat/completions', '/models'))
            elif url.endswith('/v1') or url.endswith('/v1/'):
                candidates.append(url.rstrip('/') + '/models')

            clean_base = url.split('/v1')[0].split('/chat')[0].rstrip('/')
            if clean_base:
                candidates.append(clean_base + '/v1/models')
                candidates.append(clean_base + '/api/tags')

        headers = {}
        if self.vct_llm_api_key:
            if is_anthropic:
                headers["x-api-key"] = self.vct_llm_api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self.vct_llm_api_key}"

        model_ids = []
        successful_candidate = None

        with httpx.Client(timeout=15) as client:
            for cand in candidates:
                try:
                    res = client.get(cand, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        if 'data' in data and isinstance(data['data'], list):
                            model_ids = [m['id'] for m in data['data'] if isinstance(m, dict) and 'id' in m]
                        elif 'models' in data and isinstance(data['models'], list):
                            model_ids = [m['name'] for m in data['models'] if isinstance(m, dict) and 'name' in m]
                        
                        if model_ids:
                            successful_candidate = cand
                            break
                except Exception as e:
                    _logger.debug("Attempting fetch model candidate %s failed: %s", cand, e)

        if not model_ids:
            # Fallback default list if scanning fails but server is active
            model_ids = ['gemma4:e4b', 'qwen3-fast:latest', 'qwen3:14b']

        model_ids.sort()
        self.env['ir.config_parameter'].sudo().set_param('vct_llm.available_models', json.dumps(model_ids))

        if not self.vct_llm_model_name or self.vct_llm_model_name not in model_ids:
            default_m = 'qwen3:14b' if 'qwen3:14b' in model_ids else ('qwen3-fast:latest' if 'qwen3-fast:latest' in model_ids else model_ids[0])
            self.vct_llm_model_name = default_m
            self.vct_llm_model_selection = default_m

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
