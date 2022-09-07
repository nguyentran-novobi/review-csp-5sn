from odoo import fields, Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import ValidationError
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

@tagged('post_install', '-at_install', 'basic_test')
class TestStartReconciliationSession(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super(TestStartReconciliationSession, cls).setUpClass()
        cls.new_bank_account = cls.copy_account(cls.company_data['default_journal_bank'].default_account_id)
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

    
    def test_start_reconciliation_session(self):
        # No current session
        action = self.new_bank_journal.action_usa_reconcile()
        self.assertEqual(action['name'], 'Begin Reconciliation')
        new_session = self.create_new_session(0, 0)
        self.assertEqual(new_session.journal_id, self.new_bank_journal)
        # Current session is existed
        action = self.new_bank_journal.action_usa_reconcile()
        self.assertEqual(action['name'], 'Bank Reconciliation')

    def test_validation_error_reconciliation_session(self):
        new_session = self.create_new_session(0, 0)
        # Set start date greater than statement ending date
        new_session.start_date = '2022-02-23'
        with self.assertRaises(ValidationError):
            new_session.open_reconcile_screen()

    def test_close_without_saving(self):
        new_session = self.create_new_session(0, 0)
        self.assertEqual(new_session.journal_id, self.new_bank_journal)
        # Current session is existed
        action = self.new_bank_journal.action_usa_reconcile()
        self.assertEqual(action['name'], 'Bank Reconciliation')
        new_session.close_without_saving()
        # 
        action = self.new_bank_journal.action_usa_reconcile()
        self.assertEqual(action['name'], 'Begin Reconciliation')

    def test_reconcile_bsl_with_invoice(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-02-22',
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 800})]
        })
        invoice.action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        statement.button_post()
        lines_vals_list = [{'id': line.id} for line in (invoice.line_ids).filtered(lambda r: r.debit)]
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_bsl_ids, [{'lines_vals_list': lines_vals_list}])
        new_session = self.create_new_session(0, 0)
        aml_ids = new_session._get_transactions()
        self.assertEqual(len(aml_ids), 1)
        lines = self.reconcile_screen.with_context({
            'model': 'usa.bank.reconciliation',
            'bank_reconciliation_data_id': new_session.id
        })._get_lines(options=[])
        self.assertEqual(len(lines), 1)
        expected_result = [
            (
                '02/02/2022',       # Date
                'partner_a',        # Payee
                '',                 # Batch Payment
                invoice.name,       # Memo
                '',                 # Check Number
                '',                 # Payment
                '$ 800.00',         # Deposit
            )
        ]
        columns = [1,2,3,4,5,6,7]
        self.assertLinesValues(lines, columns, expected_result)
    
    def test_reconcile_bsl_with_invoice_open_balance(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-02-22',
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 500})]
        })
        invoice.action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        statement.button_post()
        lines_vals_list = [{'id': line.id} for line in (invoice.line_ids).filtered(lambda r: r.debit)]
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_bsl_ids, [{'lines_vals_list': lines_vals_list}])
        new_session = self.create_new_session(0, 0)
        aml_ids = new_session._get_transactions()
        self.assertEqual(len(aml_ids), 2)
        lines = self.reconcile_screen.with_context({
            'model': 'usa.bank.reconciliation',
            'bank_reconciliation_data_id': new_session.id
        })._get_lines(options=[])
        self.assertEqual(len(lines), 2)
        expected_result = [
            (
                '02/02/2022',               # Date
                'partner_a',                # Payee
                '',                         # Batch Payment
                'Deposit: Open Balance',    # Memo
                '',                         # Check Number
                '',                         # Payment
                '$ 300.00',                 # Deposit
            ),
            (
                '02/02/2022',               # Date
                'partner_a',                # Payee
                '',                         # Batch Payment
                invoice.name,               # Memo
                '',                         # Check Number
                '',                         # Payment
                '$ 500.00',                 # Deposit
            )
        ]
        columns = [1,2,3,4,5,6,7]
        self.assertLinesValues(sorted(lines, key = lambda l : l['id']), columns, expected_result)

    def test_reconcile_bsl_with_bill(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-02-22',
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 500})]
        })
        bill.action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_bsl_ids = statement.line_ids.filtered(lambda line: line.amount < 0).ids
        statement.button_post()
        lines_vals_list = [{'id': line.id} for line in (bill.line_ids).filtered(lambda r: r.credit)]
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_bsl_ids, [{'lines_vals_list': lines_vals_list}])
        new_session = self.create_new_session(0, 0)
        aml_ids = new_session._get_transactions()
        self.assertEqual(len(aml_ids), 1)
        lines = self.reconcile_screen.with_context({
            'model': 'usa.bank.reconciliation',
            'bank_reconciliation_data_id': new_session.id
        })._get_lines(options=[])
        self.assertEqual(len(lines), 1)
        expected_result = [
            (
                '02/02/2022',       # Date
                'partner_a',        # Payee
                '',                 # Batch Payment
                '',                 # Memo
                '',                 # Check Number
                '$ 500.00',         # Payment
                '',                 # Deposit
            )
        ]
        columns = [1,2,3,4,5,6,7]
        self.assertLinesValues(lines, columns, expected_result)

    def test_reconcile_bsl_with_payment(self):
        new_payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': 800,
            'journal_id': self.new_bank_journal.id,
            'partner_id': self.partner_a.id,
            'date': '2022-02-22',
        })
        new_payment.action_post()
        statement = self.env['account.bank.statement'].create(self.statement_data)
        to_reconcile_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        lines_vals_list = [{'id': line.id} for line in new_payment.line_ids.filtered(lambda r: r.debit)]
        statement.button_post()
        self.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_bsl_ids, [{'lines_vals_list': lines_vals_list}])
        new_session = self.create_new_session(0, 0)
        aml_ids = new_session._get_transactions()
        # Test liquidity line of payment
        liquidity_line, _, _ = new_payment._seek_for_lines()
        self.assertEqual(aml_ids[0], liquidity_line)
        lines = self.reconcile_screen.with_context({
            'model': 'usa.bank.reconciliation',
            'bank_reconciliation_data_id': new_session.id
        })._get_lines(options=[])
        self.assertEqual(lines[0]['caret_options'], 'account.payment')
        expected_result = [
            (
                '02/22/2022',       # Date
                'partner_a',        # Payee
                '',                 # Batch Payment
                'Customer Payment $ 800.00 - partner_a - 02/22/2022', # Memo
                '',                 # Check Number
                '',                 # Payment
                '$ 800.00',         # Deposit
            )
        ]
        columns = [1,2,3,4,5,6,7]
        self.assertLinesValues(lines, columns, expected_result)

        # Create batch payment
        batch_payment = self.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-02-22',
            'journal_id': self.new_bank_journal.id,
            'payment_ids': [Command.link(new_payment.id)],
        })

        lines = self.reconcile_screen.with_context({
            'model': 'usa.bank.reconciliation',
            'bank_reconciliation_data_id': new_session.id
        })._get_lines(options=[])
        expected_result = [
            (
                '02/22/2022',       # Date
                'partner_a',        # Payee
                batch_payment.name + ' $ 800.00',                        # Batch Payment
                'Customer Payment $ 800.00 - partner_a - 02/22/2022', # Memo
                '',                 # Check Number
                '',                 # Payment
                '$ 800.00',         # Deposit
            )
        ]
        self.assertLinesValues(lines, columns, expected_result)
        
    def create_new_session(self, beginning_balance, ending_balance, statement_ending_date='2022-02-22'):
        action = self.new_bank_journal.action_usa_reconcile()
        context = action['context']
        new_session_form = Form(self.env['account.bank.reconciliation.data'].with_context(context), 'l10n_us_accounting.bank_reconciliation_data_popup_form')
        new_session_form.beginning_balance = beginning_balance
        new_session_form.ending_balance = ending_balance
        new_session_form.statement_ending_date = statement_ending_date
        new_session = new_session_form.save()
        return new_session


        

    
