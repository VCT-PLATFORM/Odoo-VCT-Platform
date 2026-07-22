# Written for VCT Platform. Not part of Odoo S.A.
{
    'name': 'VCT Helpdesk — Bảo mật dữ liệu (NĐ13)',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Tự che số thẻ/CCCD/SĐT trong ticket + chính sách lưu trữ (archive) — hỗ trợ tuân thủ NĐ 13/2023',
    'author': 'VCT Platform',
    'license': 'LGPL-3',
    'depends': ['vct_helpdesk'],
    'data': [
        'security/ir.model.access.csv',
        'data/vct_cs_privacy_config_data.xml',
        'data/ir_cron.xml',
        'views/vct_cs_privacy_config_views.xml',
    ],
    'installable': True,
}
