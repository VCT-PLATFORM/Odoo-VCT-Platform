# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Bảng chấm công: Duyệt',
    'version': '1.0',
    'category': 'Services/Timesheets',
    'sequence': 65,
    'summary': 'Duyệt và khoá dòng chấm công',
    'description': """
Bổ sung luồng duyệt cho phần Chấm công mà Odoo Community đã có sẵn (hr_timesheet):
người duyệt xác nhận các dòng chấm công, dòng đã duyệt bị khoá nên nhân viên
không sửa hay xoá được nữa; muốn sửa thì người duyệt phải bỏ duyệt trước.

KHÔNG bao gồm lưới nhập giờ kiểu bảng tính. Đó là view 'grid' (module web_grid)
và nó chỉ có trong Odoo Enterprise, không thể tái tạo từ Community. Dùng view
Danh sách và Pivot sẵn có để nhập và tổng hợp giờ.

Đây là bản dựng riêng, không phải bản sao module Timesheets của Odoo Enterprise:
dữ liệu và cấu trúc không tương thích với module đó.
""",
    'website': 'https://www.odoo.com/app/timesheet',
    # base already ships this app's icon for its Enterprise teaser card
    'icon': '/base/static/img/icons/timesheet_grid.png',
    'depends': ['hr_timesheet', 'project'],
    'data': [
        'data/timesheet_grid_data.xml',
        'views/hr_timesheet_views.xml',
        'views/project_task_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
