from odoo import Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import UserError
from .common import TestInvoicingCommonUSAccounting


@tagged('post_install', '-at_install', 'basic_test')
class TestApplyExlcudeBankStatementLines(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.receivable_account = cls.partner_a.property_account_receivable_id

        # Bank journals
        cls.bank_journal_usd = cls.company_data['default_journal_bank']

        # Bank statement
        cls.bank_statement = cls.env['account.bank.statement'].create({
            'name': 'Bank statement USD',
            'balance_start': 0.0,
            'balance_end_real': 400,
            'date': '2022-01-30',
            'journal_id': cls.bank_journal_usd.id
        })
        cls.bsl_deposit_1 = cls.env['account.bank.statement.line'].create({
            'amount': 300,
            'date': '2022-01-30',
            'payment_ref': 'Deposit 1',
            'statement_id': cls.bank_statement.id,
            'partner_id': cls.partner_a.id
        })
        cls.bsl_deposit_2 = cls.env['account.bank.statement.line'].create({
            'amount': 200,
            'date': '2022-01-30',
            'payment_ref': 'Deposit 2',
            'statement_id': cls.bank_statement.id
        })
        cls.bsl_payment = cls.env['account.bank.statement.line'].create({
            'amount': -100,
            'date': '2022-01-30',
            'payment_ref': 'Payment',
            'statement_id': cls.bank_statement.id
        })
        cls.bank_statement.button_post()

        # Payment and invoice
        cls.payment_200 = cls.create_payment(
            partner_id=cls.partner_a.id, amount=200, date='2022-01-01', auto_validate=True)
        cls.out_invoice_50 = cls.create_customer_invoice(
            amount=50, partner_id=cls.partner_a.id, date='2022-01-01', auto_validate=True)

    def test_exclude_and_undo_exclude_bank_statement_line(self):
        # Check statement lines in review screen
        bank_review_action = self.bank_statement.action_bank_reconcile_bank_statements()
        bsl_ids = bank_review_action['context']['statement_line_ids']
        self.assertTrue(
            all(line.status == 'open' for line in self.bank_statement.line_ids))
        self.assertEqual(bsl_ids.sort(), [
            self.bsl_deposit_1.id,
            self.bsl_deposit_2.id,
            self.bsl_payment.id
        ].sort())

        # Exlcude bank statement line
        self.bsl_deposit_1.action_exclude()
        bsl_to_review_data = self.env['account.reconciliation.widget'].get_bank_statement_data(
            bank_review_action['context']['statement_line_ids'], srch_domain=[])
        bsl_ids = [line['st_line']['id']
                   for line in bsl_to_review_data['lines']]
        self.assertEqual(self.bsl_deposit_1.status, 'excluded')
        self.assertEqual(bsl_ids.sort(), [
            self.bsl_deposit_2.id,
            self.bsl_payment.id
        ].sort())

        # Undo exclude bank statement line
        self.bsl_deposit_1.button_undo_exclude()
        bsl_to_review_data = self.env['account.reconciliation.widget'].get_bank_statement_data(
            bank_review_action['context']['statement_line_ids'], srch_domain=[])
        bsl_ids = [line['st_line']['id']
                   for line in bsl_to_review_data['lines']]
        self.assertEqual(self.bsl_deposit_1.status, 'open')
        self.assertEqual(bsl_ids.sort(), [
            self.bsl_deposit_1.id,
            self.bsl_deposit_2.id,
            self.bsl_payment.id
        ].sort())

    def test_review_and_undo_review_bank_statement_line(self):
        # Review bank statement line
        lines_vals_list = [{'id': line.id} for line in (
            self.payment_200.line_ids + self.out_invoice_50.line_ids).filtered(lambda r: r.debit)]
        self.env['account.reconciliation.widget'].process_bank_statement_line(
            self.bsl_deposit_1.ids, [{'lines_vals_list': lines_vals_list}])
        self.assertEqual(self.bsl_deposit_1.status, 'confirm')

        # Check temporary_reconciled field of move lines of statement line
        ar_lines = self.bsl_deposit_1.move_id.line_ids.filtered(lambda r: r.account_id == self.receivable_account)
        other_lines = self.bsl_deposit_1.move_id.line_ids - ar_lines
        self.assertEqual(len(ar_lines), 2)
        self.assertEqual(len(other_lines), 2)
        self.assertTrue(all(line.temporary_reconciled for line in ar_lines))
        self.assertFalse(all(line.temporary_reconciled for line in other_lines))

        # Check temporary_reconciled field of move lines of payment
        liquidity_line = self.payment_200.line_ids.filtered(lambda r: r.debit)
        self.assertTrue(liquidity_line.temporary_reconciled)

        # Undo review bank statement line
        self.bsl_deposit_1.button_undo_review()
        self.assertEqual(self.bsl_deposit_1.status, 'open')

        # Check temporary_reconciled field of move lines of statement line
        self.assertEqual(len(self.bsl_deposit_1.move_id.line_ids), 2)
        self.assertFalse(all(line.temporary_reconciled for line in self.bsl_deposit_1.move_id.line_ids))

        # Check temporary_reconciled field of move lines of payment
        liquidity_line = self.payment_200.line_ids.filtered(lambda r: r.debit)
        self.assertFalse(liquidity_line.temporary_reconciled)

    def test_reset_bank_statement_to_new(self):
        # Review bank statement line
        lines_vals_list = [{'id': line.id} for line in (
            self.payment_200.line_ids + self.out_invoice_50.line_ids).filtered(lambda r: r.debit)]
        self.env['account.reconciliation.widget'].process_bank_statement_line(
            self.bsl_deposit_1.ids, [{'lines_vals_list': lines_vals_list}])
        self.assertEqual(self.bsl_deposit_1.status, 'confirm')

        # Exlcude bank statement line
        self.bsl_deposit_2.action_exclude()

        # Reset bank statement to new
        self.bank_statement.button_reopen()

        # Check BSL status
        self.assertEqual(self.bsl_deposit_1.status, 'open')
        self.assertEqual(self.bsl_deposit_2.status, 'open')

    def test_undo_review_and_undo_exclude_open_statement_line(self):
        with self.assertRaises(UserError):
            self.bsl_deposit_1.button_undo_review()
        
        with self.assertRaises(UserError):
            self.bsl_deposit_2.button_undo_exclude()
