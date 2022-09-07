# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # ==== Business fields ====
    recurring_transaction_id = fields.Many2one('recurring.transaction', string='Recurring Templates')
