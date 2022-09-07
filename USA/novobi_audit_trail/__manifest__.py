# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Audit Trail',
    'summary': 'Novobi: Audit Trail',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.0',
    'license': 'OPL-1',
    'depends': [
        'base',
        'sale',
        'l10n_us_accounting',
    ],
    'data': [
        # ============================== SECURITY ================================
        'security/ir.model.access.csv',
        # ============================== DATA ================================
        'data/default_audit_rules.xml',
        # ============================== VIEW ================================
        'views/audit_trail_rule_views.xml',
        'data/audit_trail_log_sequence.xml',
        # ============================== VIEW ================================
        'views/audit_trail_log_views.xml',
    ],
    'application': False,
    'installable': True,
}
