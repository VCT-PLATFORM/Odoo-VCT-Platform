# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Cho thuê',
    'version': '19.0.1.0.0',
    'category': 'Sales/Rental',
    'summary': 'Cho thuê sản phẩm (thay Enterprise Rental): đơn thuê nhận–trả, giá theo thời lượng, kiểm trùng lịch, hoá đơn',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['sale', 'account'],
    'data': [
        'security/rental_security.xml',
        'security/ir.model.access.csv',
        'data/rental_data.xml',
        'views/product_views.xml',
        'views/rental_order_views.xml',
        'views/rental_menus.xml',
    ],
    'application': True,
    'installable': True,
}
