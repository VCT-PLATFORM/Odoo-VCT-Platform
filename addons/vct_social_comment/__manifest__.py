# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Quản lý bình luận FB (Pancake)',
    'version': '19.0.1.0.0',
    'category': 'Sales/Social',
    'summary': 'Kéo bình luận bài đăng Facebook về, phát hiện ý định mua, trả lời/ẩn, chốt đơn từ bình luận (kiểu Pancake)',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_social_sales'],
    'data': [
        'security/ir.model.access.csv',
        'views/fb_post_views.xml',
        'views/fb_comment_views.xml',
        'views/comment_reply_wizard_views.xml',
        'views/social_comment_menus.xml',
    ],
    'application': True,
    'installable': True,
}
