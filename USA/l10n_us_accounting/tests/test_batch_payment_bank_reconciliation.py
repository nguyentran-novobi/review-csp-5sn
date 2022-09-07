from odoo import Command
from odoo.tests.common import Form, tagged
from datetime import date
from .common import TestInvoicingCommonUSAccounting


@tagged('post_install', '-at_install', 'basic_test')
class TestBatchPaymentBankReconciliation(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Outstanding accounts from setting
        cls.payment_debit_account = cls.company.account_journal_payment_debit_account_id
        cls.payment_credit_account = cls.company.account_journal_payment_credit_account_id

        # Create assets account
        cls.account_asset_1 = cls.copy_account(cls.company_data['default_account_assets'])
        cls.account_asset_2 = cls.copy_account(cls.company_data['default_account_assets'])

        # Bank journal
        cls.bank_journal_usd = cls.company_data['default_journal_bank']

        # Set currency rates
        cls.env.ref('base.EUR').write({
            'rate_ids': [Command.clear(), Command.create({
                'name': '2022-01-01',
                'rate': 0.8,
            }), Command.create({
                'name': '2022-01-10',
                'rate': 0.85,
            })]
        })

        # Customer payments USD
        cls.payment_500_usd = cls.create_payment(
            partner_id=cls.partner_a.id, amount=500, date='2022-01-01', auto_validate=True)
        cls.payment_300_usd = cls.create_payment(
            partner_id=cls.partner_b.id, amount=300, date='2022-01-01', auto_validate=True)

        # Adjustment lines data
        fund_line_commands = [
            Command.create({
                'line_payment_date': '2022-01-1',
                'line_partner_id': cls.partner_a.id,
                'line_account_id': cls.account_asset_1.id,
                'line_communication': 'Line 1',
                'line_amount': 15.25
            }),
            Command.create({
                'line_payment_date': '2022-01-15',
                'line_partner_id': cls.partner_b.id,
                'line_account_id': cls.account_asset_2.id,
                'line_communication': 'Line 2',
                'line_amount': -20.48
            })
        ]

        # Batch payment inbound
        cls.batch_inbound_usd = cls.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_usd.id,
            'payment_ids': [Command.link(cls.payment_500_usd.id), Command.link(cls.payment_300_usd.id)],
            'payment_method_id': cls.env.ref('account.account_payment_method_manual_in').id,
            'fund_line_ids': fund_line_commands
        })

        # Bank statement
        cls.bank_statement = cls.env['account.bank.statement'].create({
            'name': 'Bank statement USD',
            'balance_start': 0.0,
            'balance_end_real': 794.77,
            'date': '2022-01-30',
            'journal_id': cls.bank_journal_usd.id
        })
        cls.bank_statement_line = cls.env['account.bank.statement.line'].create({
            'amount': 794.77,
            'date': '2022-01-30',
            'payment_ref': 'Deposit',
            'statement_id': cls.bank_statement.id
        })
        cls.bank_statement.button_post()

        # Bank reconciliation session
        cls.session = cls.env['account.bank.reconciliation.data'].create({
            'journal_id': cls.bank_journal_usd.id,
            'beginning_balance': 0,
            'ending_balance': 794.77,
            'statement_ending_date': '2022-01-30'
        })

    def test_batch_payment_state_after_bank_reconciliation_session(self):
        # Check batch payment state
        self.assertEqual(self.batch_inbound_usd.state, 'draft')
        # Validate batch payment
        self.batch_inbound_usd.validate_batch_button()
        # Review batch payment with bank statement line
        deposit_reconciliation_lines = self.env['account.reconciliation.widget'].get_move_lines_by_batch_payment(
            self.bank_statement_line.id, self.batch_inbound_usd.id)
        lines_vals_list = [{'id': line['id']} for line in deposit_reconciliation_lines]
        self.env['account.reconciliation.widget'].process_bank_statement_line(
            self.bank_statement_line.ids, [{'lines_vals_list': lines_vals_list}])
        # Do bank reconciliation session
        aml_ids = self.session._get_transactions()
        aml_ids.mark_bank_reconciled()
        self.assertEqual(self.batch_inbound_usd.state, 'reconciled')
        # Undo bank reconciliation session
        aml_ids.undo_bank_reconciled()
        self.assertEqual(self.batch_inbound_usd.state, 'sent')

    def test_batch_payment_state_after_setting_to_draft_adjustment_line(self):
        # Validate batch payment
        self.batch_inbound_usd.validate_batch_button()
        # Review batch payment with bank statement line
        deposit_reconciliation_lines = self.env['account.reconciliation.widget'].get_move_lines_by_batch_payment(
            self.bank_statement_line.id, self.batch_inbound_usd.id)
        lines_vals_list = [{'id': line['id']} for line in deposit_reconciliation_lines]
        self.env['account.reconciliation.widget'].process_bank_statement_line(
            self.bank_statement_line.ids, [{'lines_vals_list': lines_vals_list}])
        # Do bank reconciliation session
        aml_ids = self.session._get_transactions()
        aml_ids.mark_bank_reconciled()
        # Reset bank_reconciled of adjustment line
        fund_line = self.batch_inbound_usd.fund_line_ids[0]
        fund_line.account_move_id.line_ids.write({'bank_reconciled': False})
        self.assertEqual(self.batch_inbound_usd.state, 'sent')
