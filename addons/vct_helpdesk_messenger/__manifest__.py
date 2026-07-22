# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — Kênh Facebook Messenger',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Kênh Facebook Messenger 2 chiều: tin nhắn Fanpage → ticket, agent trả lời trong chatter → gửi ra Messenger',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk'],
    'data': [
        'security/ir.model.access.csv',
        'views/vct_messenger_account_views.xml',
        'views/vct_messenger_conversation_views.xml',
    ],
    'installable': True,
}
