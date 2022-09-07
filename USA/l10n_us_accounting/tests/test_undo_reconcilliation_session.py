from odoo import fields, Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import ValidationError, UserError
from .common import TestInvoicingCommonUSAccounting

@tagged('post_install', '-at_install', 'basic_test')
class TestUndoReconciliationSession(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls):
        super(TestUndoReconciliationSession, cls).setUpClass()
        cls.new_bank_journal = cls.env['account.journal'].create({'name': 'New Bank', 'type': 'bank', 'code': 'NB'})
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

        # New discrepancy account
        cls.discrepancy_account = cls.copy_account(cls.company_data['default_journal_bank'].default_account_id)


    def test_undo_null_previous_session(self):
        session = self.create_new_session(self.new_bank_journal, 0, 0)
        with self.assertRaises(UserError):
            session.undo_last_reconciliation()
    
    def test_undo_previous_session(self):
        in_payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': 800,
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
        (in_payment + out_payment).action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_debit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        to_reconcile_credit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount < 0).ids
        debit_lines_vals_list = [{'id': line.id} for line in in_payment.line_ids.filtered(lambda line: line.debit)]
        credit_lines_vals_list = [{'id': line.id} for line in out_payment.line_ids.filtered(lambda line: line.credit)]
        statement.button_post()
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_debit_bsl_ids, [{'lines_vals_list': debit_lines_vals_list}])
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_credit_bsl_ids, [{'lines_vals_list': credit_lines_vals_list}])
        session = self.create_new_session(self.new_bank_journal, 0, 300)
        aml_ids = session._get_transactions()
        reconcile_status = aml_ids.mapped('temporary_reconciled')
        self.assertEqual(reconcile_status, [True, True])
        action = session.check_difference_amount(
            aml_ids = [],
            difference = 300,
            cleared_payments = 500,
            cleared_deposits = 800
        )
        discrepancy_form = Form(self.env['account.bank.reconciliation.difference'].with_context(action['context']))
        discrepancy_form.reconciliation_discrepancies_account_id = self.discrepancy_account
        discrepancy_form.save().apply()
        self.assertEqual(session.state, 'reconciled')
        # Undo bank reconciliation
        session.previous_reconciliation_id = session
        session._undo()
        self.assertEqual(session.state, 'draft')
        reverse_aml_ids = session._get_transactions()
        self.assertEqual(reverse_aml_ids, aml_ids)
        

    
