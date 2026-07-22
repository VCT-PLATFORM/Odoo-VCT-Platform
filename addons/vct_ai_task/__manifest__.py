# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT AI Task — Giao việc cho AI',
    'version': '19.0.2.0.0',
    'category': 'Productivity/AI',
    'summary': 'Giao việc cho Trợ lý AI: bản ghi có trạng thái, chạy nền, định kỳ, từ Hoạt động',
    'description': """
Biến Trợ lý AI thành trợ lý GIAO VIỆC:
- Việc giao AI dạng bản ghi có trạng thái, chạy nền, kết quả định dạng đẹp.
- Nút "Giao cho AI" trên hoá đơn / phiếu / đơn hàng bất kỳ (theo bối cảnh bản ghi).
- Việc định kỳ (mỗi sáng, mỗi tuần...).
- Giao một Hoạt động (mail.activity) cho AI như giao cho nhân viên.
Dùng lại agent của vct_llm_assistant, chạy theo quyền người giao.
    """,
    'author': 'VCT Platform',
    'depends': ['vct_llm_assistant', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_activity_type.xml',
        'data/ir_cron.xml',
        'views/vct_ai_task_views.xml',
        'views/vct_ai_task_schedule_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
