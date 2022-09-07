from odoo import fields, Command
from odoo.tests.common import Form, tagged
from .common import TestInvoicingCommonUSAccounting

@tagged('post_install', '-at_install', 'basic_test')
class TestReconcileReconciliationSession(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls):
        super(TestReconcileReconciliationSession, cls).setUpClass()
        # New bank journal
        cls.new_bank_journal = cls.env['account.journal'].create({'name': 'New Bank', 'type': 'bank', 'code': 'NB'})
        # New credit card journal
        cls.credit_card_account = cls.copy_account(cls.company_data['default_journal_bank'].default_account_id)
        cls.credit_card_journal = cls.env['account.journal'].create({
            'name': 'Credit Card', 
            'type': 'bank', 
            'code': 'CC', 
            'default_account_id': cls.credit_card_account.id,
            'is_credit_card': True,
            'partner_id': cls.partner_a.id
        })

        # New discrepancy account
        cls.discrepancy_account = cls.copy_account(cls.company_data['default_journal_bank'].default_account_id)

        cls.statement_data = {
            'name': 'BNK1',
            'date': '2022-02-02',
            'journal_id': cls.new_bank_journal.id,
            'line_ids': [
                Command.create({'payment_ref': 'Deposit', 'amount': 800.0, 'partner_id': cls.partner_a.id}),
                Command.create({'payment_ref': 'Payment', 'amount': -500.0, 'partner_id': cls.partner_a.id})
                ],
        }
        cls.reconcile_screen = cls.env['usa.bank.reconciliation']

    def test_reconcile_with_positive_adjusment_amount(self):
        reconciliation_session = self.create_new_session(self.new_bank_journal, 0, 100)
        action = reconciliation_session.check_difference_amount(
            aml_ids = [],
            difference = 100,
            cleared_payments = 0,
            cleared_deposits = 0
        )
        self.assertTrue(action['name'], "Difference Amount isn't balance ($ 0.00) yet")
        context = action['context']
        self.create_discrepancy(context)
        discrepancy_move = reconciliation_session.discrepancy_entry_id
        discrepancy_move_line = discrepancy_move.line_ids.filtered(lambda line: line.credit)
        self.assertEqual(1,1)
        expected_result = [{
            'credit': 100.0,
            'account_id': self.discrepancy_account.id,
            
        }]
        self.assertRecordValues(discrepancy_move_line, expected_result)

    def test_reconcile_with_negative_adjusment_amount(self):
        reconciliation_session = self.create_new_session(self.new_bank_journal, 0, -100)
        action = reconciliation_session.check_difference_amount(
            aml_ids = [],
            difference = -100,
            cleared_payments = 0,
            cleared_deposits = 0
        )
        self.assertTrue(action['name'], "Difference Amount isn't balance ($ 0.00) yet")
        context = action['context']
        self.create_discrepancy(context)
        discrepancy_move = reconciliation_session.discrepancy_entry_id
        discrepancy_move_line = discrepancy_move.line_ids.filtered(lambda line: line.debit)
        self.assertEqual(1,1)
        expected_result = [{
            'debit': 100.0,
            'account_id': self.discrepancy_account.id,
            
        }]
        self.assertRecordValues(discrepancy_move_line, expected_result)

    def test_reconcile_with_credit_card(self):
        reconciliation_session = self.create_new_session(self.credit_card_journal, 0, -1234)
        action = reconciliation_session.check_difference_amount(
            aml_ids = [],
            difference = 0,
            cleared_payments = 0,
            cleared_deposits = 0
        )
        self.assertEqual(action['name'], 'Your credit card has been reconciled!')
        record_ending_balance_form = Form(self.env[action['res_model']].with_context(action['context']), 'l10n_us_accounting.view_record_ending_balance_form')
        # Record a bill and pay now
        record_ending_balance_form.options = 'create_purchase_receipt'
        record_ending_balance_form.payment_journal_id = self.new_bank_journal
        record_ending_balance = record_ending_balance_form.save()
        paid_bill_id = record_ending_balance.apply()['res_id']
        paid_bill = self.env['account.move'].browse([paid_bill_id])
        expected_result = [{
            'amount_total': 1234.0,
            'payment_state': 'in_payment',
            'state': 'posted'
        }]
        self.assertRecordValues(paid_bill, expected_result)
        # Record a bill and pay later
        record_ending_balance.options = 'create_vendor_bill'
        unpaid_bill_id = record_ending_balance.apply()['res_id']
        unpaid_bill = self.env['account.move'].browse([unpaid_bill_id])
        expected_result = [{
            'amount_total': 1234.0,
            'payment_state': 'not_paid',
            'state': 'draft'
        }]
        self.assertRecordValues(unpaid_bill, expected_result)
        # Do it later
        record_ending_balance.options = 'open_report'
        action = record_ending_balance.apply()
        self.assertEqual(action['name'], 'Reconciliation Reports')
    
    def test_reconcile_session(self):
        in_payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': 500,
            'journal_id': self.new_bank_journal.id,
            'partner_id': self.partner_a.id,
            'date': '2022-02-22',
        })

        out_payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'customer',
            'amount': 500,
            'journal_id': self.new_bank_journal.id,
            'partner_id': self.partner_a.id,
            'date': '2022-02-22',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-02-22',
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 300})]
        })
        invoice.action_post()
        (in_payment + out_payment).action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_debit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        to_reconcile_credit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount < 0).ids
        debit_lines_vals_list = [{'id': line.id} for line in (in_payment.line_ids + invoice.line_ids).filtered(lambda line: line.debit)]
        credit_lines_vals_list = [{'id': line.id} for line in out_payment.line_ids.filtered(lambda line: line.credit)]
        statement.button_post()
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_debit_bsl_ids, [{'lines_vals_list': debit_lines_vals_list}])
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_credit_bsl_ids, [{'lines_vals_list': credit_lines_vals_list}])
        session = self.create_new_session(self.new_bank_journal, 0, 300)
        aml_ids = session._get_transactions()
        reconcile_status = aml_ids.mapped('temporary_reconciled')
        self.assertTrue(all(reconcile_status))
        action = session.check_difference_amount(
            aml_ids = [],
            difference = 0,
            cleared_payments = 500,
            cleared_deposits = 800
        )
        expected_result = [{
            'ending_balance': 300.0,
            'deposits_cleared': 800.0,
            'payments_cleared': 500.0,
            'state': 'reconciled'
        }]
        self.assertRecordValues(session, expected_result)
        

    def create_discrepancy(self, context):
        discrepancy_form = Form(self.env['account.bank.reconciliation.difference'].with_context(context))
        discrepancy_form.reconciliation_discrepancies_account_id = self.discrepancy_account
        discrepancy_form.save().apply()
