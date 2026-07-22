# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Helpdesk',
    'version': '1.0',
    'category': 'Services/Helpdesk',
    'sequence': 60,
    'summary': 'Track, prioritize and solve customer support tickets',
    'website': 'https://www.odoo.com/app/helpdesk',
    # base already ships this app's icon for its "upgrade to Enterprise" teaser
    'icon': '/base/static/img/icons/helpdesk.png',
    'depends': ['mail', 'portal', 'rating', 'resource'],
    'data': [
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_sla_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_portal_templates.xml',
        'views/helpdesk_menus.xml',
        'views/res_config_settings_views.xml',
        'data/mail_template_data.xml',
        'data/helpdesk_data.xml',
    ],
    'application': True,
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
