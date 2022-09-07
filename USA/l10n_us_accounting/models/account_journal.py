from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_credit_card = fields.Boolean(string='Is Credit Card?')
    partner_id = fields.Many2one('res.partner', string='Vendor',
                                 help='This contact will be used to record vendor bill and payment '
                                      'for credit card balance.',
                                 copy=False)
    show_transactions_from = fields.Date(string='Show transaction from',
                                         help='Save the last start_date value in bank reconciliation screen')

    def get_all_journals_outstanding_accounts(self):
        """
        Helper: Return all outstanding accounts of journals
        """
        setting_liquid_accounts = self.mapped('company_id.account_journal_payment_debit_account_id') \
                                  + self.mapped('company_id.account_journal_payment_credit_account_id')
        journal_liquid_accounts = (self.inbound_payment_method_line_ids + self.outbound_payment_method_line_ids)\
            .mapped('payment_account_id')

        return setting_liquid_accounts + journal_liquid_accounts

    @api.constrains('currency_id')
    def _check_currency_id(self):
        for record in self:
            new_currency = record.currency_id or record.company_id.currency_id
            bank_reconciliations = self.env['account.bank.reconciliation.data'].search_count(
                [('journal_id', '=', record.id), ('currency_id', '!=', new_currency.id)])
            if bank_reconciliations:
                raise ValidationError(
                    _('Cannot change journal currency because there is bank reconciliation data in a different foreign currency.'))
