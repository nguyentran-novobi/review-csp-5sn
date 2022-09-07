# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Common Module for Accounting',
    'summary': 'Novobi: Common Module for Accounting',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Web',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'web',
        'base',
    ],
    'qweb': ['static/src/xml/*.xml'],
    "application": False,
    "installable": True,
    'assets': {
        'web.assets_backend': [
            'l10n_common/static/src/scss/usa_account_report.scss',
            'l10n_common/static/src/js/list_view.js'
        ]
    },
}
