# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi US Accounting',
    'summary': 'Novobi US Accounting',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'account_accountant',
        'l10n_us_reports',
        'contacts',
        'account_batch_payment',
        'l10n_us_check_printing',
        'account_followup',
        'l10n_common',
        'novobi_batch_adjustment'
    ],

    'data': [
        # ============================== DATA ================================
        'data/account_bank_statement_data.xml',
        'data/vendor_1099_report_data.xml',
        'data/account_type_data.xml',
        'data/account_financial_report_data.xml',
        'data/usa_bank_reconciliation_data.xml',

        # ============================== MENU ================================

        # ============================== VIEWS ===============================
        'views/res_config_settings_views.xml',
        'views/account_move_view.xml',
        'views/account_move_view.xml',
        'views/followup_view.xml',
        'views/account_payment_view.xml',
        'views/res_partner_view.xml',
        'views/ir_qweb_widget_templates.xml',
        'views/account_payment_line_view.xml',
        'views/account_bank_statement_views.xml',
        'views/account_bank_reconciliation_data_view.xml',
        'views/account_journal_dashboard_views.xml',
        'views/account_account_views.xml',
        'views/account_move_line_view.xml',
        'views/usa_1099_report.xml',
        'views/account_journal_view.xml',
        'views/usa_bank_reconciliation_views.xml',
        'views/account_journal_view.xml',

        # ============================== WIZARDS =============================
        'wizard/account_invoice_partial_payment_view.xml',
        'wizard/account_invoice_refund_usa_views.xml',
        'wizard/multiple_writeoff_views.xml',
        'wizard/button_set_to_draft_message_view.xml',
        'wizard/account_bank_reconciliation_difference_view.xml',
        'wizard/account_record_ending_balance_view.xml',
        
        # ============================== SECURITY ============================
        'security/ir.model.access.csv',

        # ============================== TEMPLATES ===========================

        # ============================== REPORT ==============================
        'report/account_followup_report_templates.xml',
        'report/print_check.xml',
        'report/vendor_1099_report_template.xml',
        'report/account_bank_reconciliation_data_report.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'l10n_us_accounting/static/src/xml/*.xml',
        ],
        'l10n_us_accounting.assets_followup_report': [
            'l10n_us_accounting/static/src/scss/account_followup_report.scss',
        ],
        'l10n_us_accounting.assets_1099_report': [
            'l10n_us_accounting/static/src/scss/report_1099.scss',
        ],
        'web.assets_backend': [
            # CSS
            'l10n_us_accounting/static/src/scss/account_followup_report.scss',
            'l10n_us_accounting/static/src/scss/account_reconciliation.scss',
            'l10n_us_accounting/static/src/scss/table_sorter.scss',
            # Javascript
            'l10n_us_accounting/static/src/js/search_by_amount_filter.js',
            'l10n_us_accounting/static/src/js/account_payment_field.js',
            'l10n_us_accounting/static/src/js/usa_1099_report.js',
            'l10n_us_accounting/static/src/js/reconciliation/reconciliation_action.js',
            'l10n_us_accounting/static/src/js/reconciliation/reconciliation_model.js',
            'l10n_us_accounting/static/src/js/reconciliation/reconciliation_renderer.js',
            'l10n_us_accounting/static/src/js/reconciliation/manual_reconciliation_renderer.js',
            'l10n_us_accounting/static/src/js/account_report/jquery.tablesorter.js',
            'l10n_us_accounting/static/src/js/account_report/usa_bank_reconciliation.js',
        ],
    },
    "application": False,
    "installable": True,
}
