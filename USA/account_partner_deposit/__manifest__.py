# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Partner Deposit',
    'summary': 'Novobi: Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'l10n_generic_coa',
        'account_reports',
        'account',
        'account_followup'
    ],

    'data': [
        # ============================== DATA =================================
        'data/coa_chart_data.xml',

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== VIEWS ================================
        'views/res_partner_view.xml',
        'views/account_payment_deposit_view.xml',
        'views/account_move_views.xml',

        # ============================== REPORT ===============================
        'report/account_followup_report_templates.xml',

        # ============================== WIZARDS ==============================
        'wizard/order_make_deposit_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'account_partner_deposit/static/src/scss/account_followup_report.scss'
        ],
        'web.assets_frontend': [],
        'web.assets_qweb': [
            'account_partner_deposit/static/src/xml/**/*',
        ],
    },
    'installable': True,
    'auto_install': False
}
