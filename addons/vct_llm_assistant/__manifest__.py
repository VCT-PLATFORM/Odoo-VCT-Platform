# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT LLM Assistant',
    'version': '19.0.2.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'AI Agent tích hợp sâu Odoo qua Discuss (tra cứu, nhập liệu, kế toán TT99)',
    'description': """
AI Agent chạy trên Claude/OpenAI, tích hợp trong Odoo Discuss.
Nhắn riêng hoặc nhắc @Trợ lý AI trong nhóm; agent đọc/ghi dữ liệu qua công cụ
gọi hàm, chạy nền theo quyền của người dùng, chặn xoá và chống prompt-injection.
    """,
    'author': 'VCT Platform',
    'depends': ['base', 'mail', 'mail_bot'],
    'data': [
        'security/ir.model.access.csv',
        'data/res_partner_data.xml',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vct_llm_assistant/static/src/css/ai_typewriter.css',
            'vct_llm_assistant/static/src/js/ai_typewriter_patch.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
