# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Ký điện tử',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Sign',
    'summary': 'Ký điện tử tài liệu PDF (thay Enterprise Sign): mẫu + vùng ký, yêu cầu ký, đóng chữ ký/ngày/tên lên PDF, hash lưu vết',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'security/sign_security.xml',
        'security/ir.model.access.csv',
        'views/sign_template_views.xml',
        'views/sign_request_views.xml',
        'views/sign_menus.xml',
    ],
    'application': True,
    'installable': True,
}
