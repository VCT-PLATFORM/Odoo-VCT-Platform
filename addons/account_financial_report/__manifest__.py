# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế toán: Báo cáo tài chính',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Mở khoá phân hệ Kế toán và thêm Bảng cân đối kế toán, Kết quả kinh doanh, Sổ cái, Bảng cân đối phát sinh',
    'depends': ['account'],
    'data': [
        'security/account_feature_groups.xml',
        'security/ir.model.access.csv',
        'views/account_financial_report_views.xml',
        'views/account_move_line_views.xml',
        'views/account_aged_report_views.xml',
        'views/account_report_menus.xml',
    ],
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
