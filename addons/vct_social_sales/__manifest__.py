# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Bán hàng đa kênh (Pancake)',
    'version': '19.0.1.0.0',
    'category': 'Sales/Social',
    'summary': 'Chốt đơn ngay từ hội thoại Zalo/Messenger (kiểu Pancake): tạo đơn bán từ chat, gom đơn từ mạng xã hội',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk_zalo', 'vct_helpdesk_messenger', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/social_order_wizard_views.xml',
        'views/conversation_views.xml',
        'views/sale_order_views.xml',
        'views/social_menus.xml',
    ],
    'application': True,
    'installable': True,
}
