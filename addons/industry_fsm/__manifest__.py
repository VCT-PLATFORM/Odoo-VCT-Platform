# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Dịch vụ hiện trường',
    'version': '1.0',
    'category': 'Services/Field Service',
    'sequence': 95,
    'summary': 'Công việc tại hiện trường: bấm giờ, ghi nhận giờ công, xác nhận hoàn thành',
    'description': """
Dựng trên module Project và Chấm công đã có sẵn: đánh dấu một dự án là dịch vụ
hiện trường, rồi bấm giờ ngay trên công việc — giờ công được ghi thành timesheet
khi dừng, và xác nhận hoàn thành sẽ tự dừng đồng hồ.

Đây là bản dựng riêng, không phải bản sao module Field Service của Odoo
Enterprise: dữ liệu và cấu trúc không tương thích với module đó.
""",
    'website': 'https://www.odoo.com/app/field-service',
    # base already ships this app's icon for its Enterprise teaser card
    'icon': '/base/static/img/icons/industry_fsm.png',
    'depends': ['project', 'hr_timesheet', 'timesheet_grid'],
    'data': [
        'data/industry_fsm_data.xml',
        'views/industry_fsm_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'application': True,
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
