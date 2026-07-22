# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế toán: Nhắc nợ khách hàng',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Theo dõi hoá đơn quá hạn và tự động gửi email nhắc nợ theo mức',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_followup_data.xml',
        'data/ir_cron_data.xml',
        'views/account_followup_views.xml',
    ],
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
