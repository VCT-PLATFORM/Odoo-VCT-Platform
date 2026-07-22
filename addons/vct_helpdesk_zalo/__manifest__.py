# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — Kênh Zalo OA',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Kênh Zalo Official Account 2 chiều: tin nhắn Zalo → ticket, agent trả lời trong chatter → gửi ra Zalo',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/vct_zalo_account_views.xml',
        'views/vct_zalo_conversation_views.xml',
    ],
    'installable': True,
}
