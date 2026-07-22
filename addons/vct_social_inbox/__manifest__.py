# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Inbox hợp nhất (Pancake)',
    'version': '19.0.1.0.0',
    'category': 'Sales/Social',
    'summary': 'Một màn hình gộp mọi hội thoại Zalo + Messenger, chốt đơn/mở hội thoại ngay trong inbox (kiểu Pancake)',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_social_sales'],
    'data': [
        'security/ir.model.access.csv',
        'views/social_thread_views.xml',
        'views/social_inbox_menus.xml',
    ],
    'installable': True,
}
