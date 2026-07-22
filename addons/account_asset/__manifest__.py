# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế toán: Tài sản cố định & Chi phí trả trước',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Khấu hao tài sản cố định và phân bổ chi phí trả trước theo kỳ',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/account_asset_views.xml',
        'views/account_asset_menus.xml',
    ],
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
