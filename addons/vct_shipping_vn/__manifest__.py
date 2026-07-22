# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Vận chuyển VN (GHN/GHTK/ViettelPost)',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Tạo vận đơn qua nhà vận chuyển VN (GHN, GHTK, ViettelPost) từ đơn bán: tính phí, mã vận đơn, tra trạng thái',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['sale', 'stock'],
    'data': [
        'security/shipping_security.xml',
        'security/ir.model.access.csv',
        'data/shipping_carrier_data.xml',
        'views/shipping_carrier_views.xml',
        'views/shipment_views.xml',
        'views/sale_order_views.xml',
        'views/shipping_menus.xml',
    ],
    'application': True,
    'installable': True,
}
