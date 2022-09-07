# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    "name": "Novobi: Recurring Transactions",
    "summary": "Novobi: Recurring Transactions",
    "author": "Novobi",
    "website": "http://www.odoo-accounting.com",
    "description": """Recurring Transaction is a part of Accounting Finance """,
    'version': '15.0.0',
    'license': 'OPL-1',
    "depends": ["mail","account"],
    "data": [
        'data/ir_cron_data.xml',
        'data/recurring_transaction_template_sequence.xml',
        'security/ir.model.access.csv',
        'views/recurring_transactions_template_views.xml',
    ],
    "application": True,
    "installable": True,
}
