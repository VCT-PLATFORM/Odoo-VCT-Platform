# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — ERP-native',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Mở rộng Helpdesk: toàn cảnh khách hàng 360°, gắn đơn/hoá đơn/bảo hành, hạng KH → SLA, tìm không dấu',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['helpdesk', 'helpdesk_repair', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/vct_cs_tier_data.xml',
        'data/resource_calendar_vn.xml',
        'views/vct_cs_tier_views.xml',
        'views/res_partner_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
