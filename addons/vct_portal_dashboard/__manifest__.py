# -*- coding: utf-8 -*-
{
    'name': 'VCT Portal Dashboard',
    'version': '19.0.3.0.0',
    'category': 'Website/Portal',
    'summary': 'Trang chủ portal dạng app launcher — chạy nội bộ hoàn toàn',
    'description': """
Ghi đè trang chủ portal (/my) thành app launcher gọn gàng, liên kết thẳng tới
các ứng dụng backend. Không có tham chiếu tài khoản/đăng ký online.
    """,
    'author': 'VCT Platform',
    'depends': ['web', 'portal'],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vct_portal_dashboard/static/src/css/portal_dashboard.css',
            'vct_portal_dashboard/static/src/js/icon_fallback.js',
        ],
        'web.assets_backend': [
            'vct_portal_dashboard/static/src/xml/navbar_override.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
