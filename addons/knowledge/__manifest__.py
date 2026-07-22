# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kiến thức',
    'version': '1.0',
    'category': 'Productivity/Knowledge',
    'sequence': 90,
    'summary': 'Kho bài viết nội bộ, phân cấp và tìm kiếm được',
    'description': """
Kho kiến thức nội bộ: bài viết phân cấp, soạn thảo rich text, đánh dấu yêu thích,
phân quyền theo nhánh (sửa được / chỉ đọc / riêng tư).

Bài viết có lịch sử phiên bản: nội dung cũ luôn khôi phục lại được.

Đây là bản dựng riêng, không phải bản sao của module Knowledge trong Odoo
Enterprise: dữ liệu và cấu trúc không tương thích với module đó.
""",
    'website': 'https://www.odoo.com/app/knowledge',
    # base already ships this app's icon for its Enterprise teaser card
    'icon': '/base/static/img/icons/knowledge.png',
    'depends': ['mail', 'html_editor'],
    'data': [
        'security/knowledge_security.xml',
        'security/ir.model.access.csv',
        'views/knowledge_article_views.xml',
        'views/knowledge_menus.xml',
        'views/res_config_settings_views.xml',
    ],
    'application': True,
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
