from odoo import fields, models, api


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """
        Override.
        Called when clicking on button `Apply` on `bank_statement_reconciliation_view` (review screen)

        :param st_line_ids
        :param list of dicts data: must contains the keys
            'counterpart_aml_dicts', 'payment_aml_ids' and 'new_aml_dicts',
            whose value is the same as described in process_reconciliation
            except that ids are used instead of recordsets.
        :returns dict: used as a hook to add additional keys.
        """
        result = super().process_bank_statement_line(st_line_ids, data)

        statement_lines = self.env['account.bank.statement.line'].browse(st_line_ids)

        # Mark BSL as reviewed
        statement_lines.write({'status': 'confirm'})

        # Mark all the lines that are not Bank or Bank Suspense Account temporary_reconcile
        statement_lines.get_reconciliation_lines().write({'temporary_reconciled': True})

        return result

    # -------------------------------------------------------------------------
    # MATCHING CONDITION
    # -------------------------------------------------------------------------
    def _get_domain_for_transaction_filters(self, statement_line):
        """
        Helper: Get domain for amount, date and transaction type filters in bank review screen
        """
        domain = []
        company = statement_line.company_id or statement_line.journal_id.company_id
        is_negative_statement_line = statement_line.currency_id.compare_amounts(statement_line.amount, 0) < 0
        if company.bank_review_date_filter:
            domain += [('date', '<=', statement_line.date)]
        if company.bank_review_transaction_type_filter:
            if is_negative_statement_line:
                domain += [('debit', '=', 0)]
            else:
                domain += [('credit', '=', 0)]
        if company.bank_review_amount_filter:
            if is_negative_statement_line:
                domain += [('credit', '<=', -statement_line.amount), ('debit', '<=', -statement_line.amount)]
            else:
                domain += [('debit', '<=', statement_line.amount), ('credit', '<=', statement_line.amount)]

        return domain

    @api.model
    def _get_query_reconciliation_widget_customer_vendor_matching_lines(self, statement_line, domain=[]):
        """
        Override
        Add more conditions to filter account move lines of Customer/Vendor Matching tab in BSL review screen
        - Transaction Date <= BSL date
        - Based on transaction type (Deposit/Payment)
        - Transactions' amount <= BSLs' amount
        - Same Payee (OOTB)
        """
        journal_domain = [
            '|', ('payment_id', '=', False),
            '&', ('payment_id', '!=', False), ('journal_id', '=', statement_line.journal_id.id)
        ]
        domain = domain + journal_domain + self._get_domain_for_transaction_filters(statement_line)

        return super(AccountReconciliation, self)._get_query_reconciliation_widget_customer_vendor_matching_lines(statement_line, domain)

    @api.model
    def _get_query_reconciliation_widget_miscellaneous_matching_lines(self, statement_line, domain=[]):
        """
        Override
        Add more conditions to filter account move lines of Miscellaneous Matching tab in BSL review screen
        - Transaction Date <= BSL date
        - Based on transaction type (Deposit/Payment)
        - Transactions' amount <= BSLs' amount
        - Same Payee (OOTB)
        """
        
        domain = domain + self._get_domain_for_transaction_filters(statement_line)

        return super(AccountReconciliation, self)._get_query_reconciliation_widget_miscellaneous_matching_lines(statement_line, domain)

    @api.model
    def get_bank_statement_data(self, bank_statement_line_ids, srch_domain=[]):
        """
        Override.
        Called when load reviewed form.
        Add status = open to `domain` in order to remove excluded/reconciled bank statement lines.
        """
        srch_domain.append(('status', '=', 'open'))
        return super().get_bank_statement_data(bank_statement_line_ids, srch_domain)

    @api.model
    def get_batch_payments_data(self, bank_statement_ids):
        """
        Override
        Filter batch payments in BSL review screen following conditions:
        - Batch payments must have same Journal as BSL
        - Batch payments type (IN/OUT) must have Same Transaction Type as BSL
        - Unreconciled amount of batch payment <= amount of BSL
        """
        batch_payments = super(AccountReconciliation, self).get_batch_payments_data(bank_statement_ids)
        length = len(batch_payments)
        index = 0

        while index < length:
            batch = batch_payments[index]
            batch_id = self.env['account.batch.payment'].browse(batch['id'])
            move_lines = batch_id.get_batch_payment_aml()
            if move_lines:
                batch.update(batch_id._get_batch_info_for_review())
                index += 1
            else:
                del batch_payments[index]
                length -= 1

        return batch_payments

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """
        Override.
        Called when clicking on button `Apply` on `bank_statement_reconciliation_view` (review screen)
        :param st_line_ids
        :param list of dicts data: must contains the keys
            'counterpart_aml_dicts', 'payment_aml_ids' and 'new_aml_dicts',
            whose value is the same as described in process_reconciliation
            except that ids are used instead of recordsets.
        :returns dict: used as a hook to add additional keys.
        """
        result = super().process_bank_statement_line(st_line_ids, data)

        statement_lines = self.env['account.bank.statement.line'].browse(st_line_ids)

        # Mark BSL as reviewed
        statement_lines.write({'status': 'confirm'})

        # Mark all the lines that are not Bank or Bank Suspense Account temporary_reconcile
        statement_lines.get_reconciliation_lines().write({'temporary_reconciled': True})

        return result
