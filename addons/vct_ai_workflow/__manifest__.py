# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT AI Workflow',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Automation',
    'summary': 'Chuỗi workflow AI Automation: thêm node AI vào engine tự động hoá Odoo',
    'description': """
Biến engine tự động hoá sẵn có của Odoo (Automation Rules + Server Actions + Cron)
thành nền tảng workflow AI: thêm loại bước 'AI Agent' chạy prompt qua Trợ lý AI,
nối chuỗi với các bước tạo/sửa bản ghi, webhook, điều kiện; có nhật ký thực thi.
    """,
    'author': 'VCT Platform',
    'depends': ['base_automation', 'vct_llm_assistant'],
    'data': [
        'security/ir.model.access.csv',
        'views/ir_actions_server_views.xml',
        'views/workflow_log_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
