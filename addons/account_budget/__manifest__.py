# -*- coding: utf-8 -*-
{
    'name': 'Budget Management',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Manage budgets and compare planned vs actual expenses/revenues',
    'description': """
This module allows you to define budgets, budgetary positions (groups of accounts),
and compare planned amounts with actual amounts from journal entries.
    """,
    'author': 'VCT Platform',
    'depends': ['account', 'analytic'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_budget_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
