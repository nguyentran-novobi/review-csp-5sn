# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi Batch Payment Adjustment',
    'summary': 'Novobi Batch Payment Adjustment',
    'author': 'Novobi',
    'website': 'https://www.novobi.com/',
    'category': 'Accounting',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'account_accountant'
    ],

    'data': [
        # ============================== DATA ================================

        # ============================== MENU ================================

        # ============================== WIZARDS =============================

        # ============================== VIEWS ===============================
        'views/account_batch_payment_views.xml',
        'views/account_move_views.xml',

        # ============================== SECURITY ============================
        'security/ir.model.access.csv',

        # ============================== TEMPLATES ===========================

        # ============================== REPORT ==============================
        'report/account_batch_payment_report_templates.xml'

    ],
    'application': False,
    'installable': True,
}
