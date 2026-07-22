# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — AI khách hàng',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'AI tự trả lời khách trên Zalo: RAG Knowledge Base + dữ liệu KH giới hạn đúng partner, tự chuyển nhân viên khi bí',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk_zalo', 'vct_llm_assistant', 'knowledge'],
    'data': [
        'security/ir.model.access.csv',
        'data/vct_cs_ai_config_data.xml',
        'data/ir_cron.xml',
        'views/vct_cs_copilot_views.xml',
        'views/vct_cs_ai_config_views.xml',
        'views/vct_cs_ai_log_views.xml',
        'views/vct_cs_qa_score_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
}
