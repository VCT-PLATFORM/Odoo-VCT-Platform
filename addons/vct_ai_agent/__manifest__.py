# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT AI Agents (Odoo AI)',
    'version': '19.0.1.0.0',
    'category': 'Productivity/AI',
    'summary': 'Khung AI Agents cấu hình được (vai trò/quy tắc/tool/mẫu lệnh) + "Hỏi AI" theo ngữ cảnh trên mọi bản ghi — tương đương Odoo AI',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_llm_assistant', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ai_agent_data.xml',
        'views/ai_agent_views.xml',
        'views/ai_ask_wizard_views.xml',
        'views/ai_agent_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
