# -*- coding: utf-8 -*-
{
    'name': 'Custom Maintenance Worksheets',
    'version': '1.0',
    'category': 'Manufacturing/Maintenance',
    'summary': 'Standardize maintenance procedures with customizable worksheets and checklists',
    'description': """
This module allows you to create custom worksheet templates (checklists, text inputs, measurements)
and link them to maintenance requests. Technicians can fill out worksheets and sign off.
    """,
    'author': 'VCT Platform',
    'depends': ['maintenance', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/worksheet_template_views.xml',
        'views/maintenance_worksheet_views.xml',
        'views/maintenance_request_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
