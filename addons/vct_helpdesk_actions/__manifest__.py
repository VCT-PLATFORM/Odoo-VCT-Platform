# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — Hành động ERP',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Từ ticket tạo việc kỹ thuật viên (FSM) và phiếu hoàn tiền/đổi trả — người xác nhận trước khi lưu',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk', 'industry_fsm'],
    'data': [
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
}
