# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'Lịch hẹn',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Online Appointment',
    'summary': 'Cho khách tự chọn khung giờ trống và đặt lịch hẹn',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['calendar', 'resource', 'website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/appointment_data.xml',
        'views/appointment_templates.xml',
        'views/appointment_views.xml',
    ],
    'application': True,
    'installable': True,
}
