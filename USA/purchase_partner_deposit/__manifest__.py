# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Purchase Partner Deposit',
    'summary': 'Novobi: Purchase Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '14.0',
    'license': 'OPL-1',
    'depends': [
        'account_partner_deposit',
        'purchase'
    ],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================
        'views/account_payment_views.xml',
        'views/purchase_order_views.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARDS ==============================
    ],
    'installable': True,
    'auto_install': False
}
