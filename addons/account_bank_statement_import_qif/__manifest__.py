# -*- coding: utf-8 -*-
{
    'name': 'QIF Bank Statement Import',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Import bank statements from .qif files',
    'description': """
This module allows you to import bank statement transactions using standard QIF format files.
    """,
    'author': 'VCT Platform',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/account_bank_statement_import_qif_views.xml',
        'views/account_journal_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
