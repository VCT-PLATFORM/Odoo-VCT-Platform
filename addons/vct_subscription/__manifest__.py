# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Thuê bao / Bán định kỳ',
    'version': '19.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Thuê bao định kỳ (thay Enterprise Subscriptions): gói định kỳ, hợp đồng thuê bao, cron sinh hoá đơn, MRR',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['sale', 'account'],
    'data': [
        'security/subscription_security.xml',
        'security/ir.model.access.csv',
        'data/subscription_data.xml',
        'views/subscription_plan_views.xml',
        'views/subscription_views.xml',
        'views/subscription_menus.xml',
    ],
    'application': True,
    'installable': True,
}
