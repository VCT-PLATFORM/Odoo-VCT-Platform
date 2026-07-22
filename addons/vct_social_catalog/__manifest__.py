# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Chia sẻ sản phẩm vào chat (Pancake)',
    'version': '19.0.1.0.0',
    'category': 'Sales/Social',
    'summary': 'Gửi nhanh thẻ sản phẩm/bảng giá vào hội thoại Zalo/Messenger (kiểu Pancake)',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_social_sales'],
    'data': [
        'security/ir.model.access.csv',
        'views/social_share_wizard_views.xml',
        'views/conversation_views.xml',
    ],
    'installable': True,
}
