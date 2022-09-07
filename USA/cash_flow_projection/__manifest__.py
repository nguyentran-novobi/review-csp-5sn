# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    "name": "Novobi: Cash Flow Projection",
    "summary": "Novobi: Cash Flow Projection",
    "author": "Novobi",
    "website": "http://www.odoo-accounting.com",
    "description": """Cash Flow Projection is a part of Accounting Finance For E-Retailers""",
    'version': '14.0',
    'license': 'OPL-1',
    "depends": [
        'purchase',
        'sale',
        'account_reports',
    ],
    "data": [
        'security/ir.model.access.csv',
        'data/cash_flow_transaction_type.xml',
        'views/assets.xml',
        'views/cash_flow_projection_view.xml',
        'views/cash_flow_transaction_type_view.xml',
        'views/res_config_settings.xml',
        'views/account_account_view.xml',
        'views/cash_flow_projection_detail_report_view.xml',
        'views/report_financial.xml',
        'wizard/so_po_lead_time_view.xml',
        'wizard/cash_flow_period_number_view.xml',
        'wizard/recurring_cash_settings_view.xml',
        'report/cash_flow_projection_template.xml',
    ],

    'assets': {
        'web.assets_qweb': [
            'cash_flow_projection/static/src/xml/*.xml',
        ],
        'web.assets_backend': [
            'cash_flow_projection/static/src/scss/cash_flow_projection.scss',
            'cash_flow_projection/static/src/js/cash_flow_projection_backend.js',
        ],
    },

    "application": False,
    "installable": True,
}
