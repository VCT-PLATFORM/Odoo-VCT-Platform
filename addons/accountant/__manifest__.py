# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế toán',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'sequence': 30,
    'summary': 'Kế toán, Thuế, Tài sản, Báo cáo tài chính',
    'website': 'https://www.odoo.com/app/accounting',
    # base ships this app's icon for its "upgrade to Enterprise" teaser
    'icon': '/base/static/img/icons/account_accountant.png',
    'depends': [
        'account',
        'account_financial_report',
        'account_asset',
        'account_followup',
        'account_reconciliation',
    ],
    'data': [
        'data/accountant_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'application': True,
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
