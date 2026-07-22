# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — Phân tích CS×ERP',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Báo cáo pivot/graph nối dữ liệu CS với ERP (hạng KH, SLA, CSAT) — kéo-thả, xuất Excel bằng công cụ gốc Odoo',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk'],
    'data': [
        'views/helpdesk_ticket_report_views.xml',
    ],
    'installable': True,
}
