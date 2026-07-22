# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Phê duyệt',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Approvals',
    'summary': 'Yêu cầu phê duyệt đa cấp (thay Enterprise Approvals): loại yêu cầu, nhiều người duyệt, ngưỡng tối thiểu, hoạt động nhắc',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'security/approval_security.xml',
        'security/ir.model.access.csv',
        'data/approval_category_data.xml',
        'views/approval_category_views.xml',
        'views/approval_request_views.xml',
        'views/approval_menus.xml',
    ],
    'application': True,
    'installable': True,
}
