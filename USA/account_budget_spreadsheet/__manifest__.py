# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'USA: Budget Spreadsheet',
    'summary': 'USA: Budget Spreadsheet',
    'category': 'Accounting',
    'author': "Novobi",
    'website': 'http://www.odoo-accounting.com',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'documents',
        'documents_spreadsheet',
        'documents_spreadsheet_account',
        'account_budget',
        'account_reports',
    ],
    'data': [
        # ============================== DATA =============================
        'data/budget_spreadsheet_data.xml',
        # ============================== VIEWS =============================
        'views/documents_views.xml',
        'views/account_financial_report_view.xml',
        # ============================== WIZARD =============================
        'wizard/account_budget_wizard_view.xml'
    ],
    'assets': {
        'web.assets_qweb': [
            "account_budget_spreadsheet/static/src/xml/budget_spreadsheet_button.xml",
        ],
        'web.assets_backend': [
            "account_budget_spreadsheet/static/src/js/budget_spreadsheet_list_view.js",
            "account_budget_spreadsheet/static/src/js/budget_spreadsheet_widget.js",
        ],
    },
    "application": False,
    "installable": True,
}
