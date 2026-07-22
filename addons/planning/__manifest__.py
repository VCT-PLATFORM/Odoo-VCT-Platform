# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế hoạch',
    'version': '1.0',
    'category': 'Services/Planning',
    'sequence': 130,
    'summary': 'Xếp ca làm việc cho nhân viên',
    'description': """
Xếp ca làm việc: tạo ca, phân công nhân viên, để ca mở cho ai rảnh nhận, cảnh báo
khi một người bị xếp trùng giờ, sao chép lịch tuần trước, lặp ca hàng tuần, và
công bố lịch cho nhân viên qua email.

Lịch hiển thị bằng view Lịch/Danh sách/Kanban của Community. Odoo Enterprise dùng
biểu đồ Gantt kéo-thả (module web_gantt), phần đó không có trong Community nên
không tái tạo được.

Đây là bản dựng riêng, không phải bản sao module Planning của Odoo Enterprise:
dữ liệu và cấu trúc không tương thích với module đó.
""",
    'website': 'https://www.odoo.com/app/planning',
    # base already ships this app's icon for its Enterprise teaser card
    'icon': '/base/static/img/icons/planning.png',
    'depends': ['hr', 'hr_holidays', 'project'],
    'data': [
        'security/planning_security.xml',
        'security/ir.model.access.csv',
        'data/planning_data.xml',
        'views/planning_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'application': True,
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
