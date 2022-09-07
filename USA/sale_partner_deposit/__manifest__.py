# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Sale Partner Deposit',
    'summary': 'Novobi: Sale Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'account_partner_deposit',
        'sale_management'
    ],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================
        'views/account_payment_views.xml',
        'views/sale_order_views.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARDS ==============================
    ],
    'installable': True,
    'auto_install': False
}
