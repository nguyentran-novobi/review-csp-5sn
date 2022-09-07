from odoo import models, fields, api, _, Command


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    @api.depends('payment_ids.move_id.is_move_sent', 'payment_ids.is_matched', 'fund_line_ids.move_state', 
        'payment_ids.move_id.line_ids.bank_reconciled', 'fund_line_ids.account_move_id.line_ids.bank_reconciled')
    def _compute_state(self):
        """
        Override to compute "reconciled" state for batch payment
        """
        super()._compute_state()

        for batch in self:
            outstanding_accounts = batch.journal_id.get_all_journals_outstanding_accounts()
            move_lines = batch.payment_ids.mapped('line_ids') + batch.fund_line_ids.mapped('account_move_id.line_ids')
            unreconciled_move_lines = move_lines.filtered(lambda l: l.account_id in outstanding_accounts
                                                                    and not l.bank_reconciled)
            if not batch.payment_ids and not batch.fund_line_ids:
                batch.state = 'draft'
            elif not unreconciled_move_lines:
                batch.state = 'reconciled'
            elif all(pay.is_move_sent for pay in batch.payment_ids) \
                and (not batch.fund_line_ids 
                    or (batch.fund_line_ids and all(line.move_state == 'posted' for line in batch.fund_line_ids))):
                batch.state = 'sent'
            else:
                batch.state = 'draft'

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def get_batch_payment_aml(self):
        """
        Get all account.move.line in batch payments, include payments and adjustments.
        """
        aml_ids = self.env['account.move.line']
        for record in self:
            journal_accounts =record.journal_id.get_all_journals_outstanding_accounts()
            journal_accounts_ids = journal_accounts.ids
            for payment in record.payment_ids.filtered(lambda p: p.state == 'posted'):
                aml_ids |= payment.line_ids.filtered(lambda r: r.account_id.id in journal_accounts_ids and not r.reconciled and not r.bank_reconciled)
            for line in record.fund_line_ids:
                line_id = line.get_aml_adjustments(journal_accounts_ids)
                aml_ids |= line_id

        return aml_ids

    def _get_batch_info_for_review(self):
        """
        Used to get info of this batch payment (except which has been reviewed (temporary_reconciled = True)).
        :return: dictionary of type, amount, amount_journal_currency, amount_payment_currency, journal_id
        """
        journal_company = self.journal_id.company_id
        def get_amount(rec_amount, currency):
            if currency == journal_currency:
                return rec_amount
            return currency._convert(rec_amount, journal_currency, journal_company, self.date or fields.Date.today())

        self.ensure_one()
        # Copy from account_batch_payment/account_batch_payment.
        company_currency = journal_company.currency_id or self.env.company.currency_id
        journal_currency = self.journal_id.currency_id or company_currency
        filter_amount = self.batch_type == 'outbound' and -self.amount or self.amount

        for payment in self.payment_ids.filtered(lambda p: p.is_matched or p.state == 'draft'):
            payment_currency = payment.currency_id or company_currency
            filter_amount -= get_amount(payment.amount, payment_currency)

        for line in self.fund_line_ids.filtered(lambda f: f.has_been_reviewed or f.account_move_id.state == 'draft'):
            line_currency = line.currency_id or company_currency
            filter_amount -= get_amount(line.line_amount, line_currency)

        return {
            # To filter in review screen.
            'bank_review_amount_filter': journal_company.bank_review_amount_filter,
            'bank_review_transaction_type_filter': journal_company.bank_review_transaction_type_filter,
            'type': self.batch_type,
            'filter_amount': filter_amount,
            'journal_id': self.journal_id.id
        }

class AccountBatchPaymentLine(models.Model):
    _inherit = 'account.batch.deposit.fund.line'

    # == Technical fields ==
    has_been_reviewed = fields.Boolean(string='Have been reviewed?', compute='_compute_bank_reconciled', store=True, copy=False)

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('account_move_id', 'account_move_id.line_ids.reconciled')
    def _compute_bank_reconciled(self):
        for record in self:
            aml_ids = record.get_aml_adjustments()
            record.has_been_reviewed = True if record.move_state == 'posted' and not aml_ids else False

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def get_aml_adjustments(self, liquid_accounts=None):
        """
        Override to filter out bank_reconciled account move lines
        """
        move_lines = super(AccountBatchPaymentLine, self).get_aml_adjustments(liquid_accounts)
        return move_lines.filtered(lambda r: not r.bank_reconciled)
