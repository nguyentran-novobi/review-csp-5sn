from odoo import Command
from odoo.tests.common import Form, tagged
from .common import TestInvoicingCommonBatchAdjustment


@tagged('post_install', '-at_install', 'basic_test')
class TestAdjustmentLinesInBankReviewScreen(TestInvoicingCommonBatchAdjustment):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Customer payments USD
        cls.payment_500_usd = cls.create_payment(
            partner_id=cls.partner_a.id, amount=500, date='2022-01-01', auto_validate=True)
        cls.payment_300_usd = cls.create_payment(
            partner_id=cls.partner_b.id, amount=300, date='2022-01-01', auto_validate=True)

        # Vendor payments USD
        cls.vendor_payment_500_usd = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_a.id, amount=500,
            date='2022-01-01', auto_validate=True)
        cls.vendor_payment_300_usd = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_b.id, amount=300,
            date='2022-01-01', auto_validate=True)

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

        # Batch payment
        cls.batch_inbound_usd = cls.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_usd.id,
            'payment_ids': [Command.link(cls.payment_500_usd.id), Command.link(cls.payment_300_usd.id)],
            'payment_method_id': cls.manual_in_method.id,
            'fund_line_ids': fund_line_commands
        })
        cls.batch_outbound_usd = cls.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_usd.id,
            'payment_ids': [Command.link(cls.vendor_payment_500_usd.id), Command.link(cls.vendor_payment_300_usd.id)],
            'payment_method_id': cls.manual_out_method.id,
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

        cls.bank_statement_payment = cls.env['account.bank.statement'].create({
            'name': 'Bank statement USD',
            'balance_start': 0.0,
            'balance_end_real': -794.77,
            'date': '2022-01-30',
            'journal_id': cls.bank_journal_usd.id
        })
        cls.bank_statement_line_payment = cls.env['account.bank.statement.line'].create({
            'amount': -794.77,
            'date': '2022-01-30',
            'payment_ref': 'Payment',
            'statement_id': cls.bank_statement_payment.id
        })
        cls.bank_statement_payment.button_post()

    def test_adjustment_lines_of_inbound_batch(self):
        self.batch_inbound_usd.validate_batch_button()

        # Check possible matching lines of batch statement in bank review screen
        deposits_reconciliation_data = self.env['account.reconciliation.widget'].get_batch_payments_data(
            self.bank_statement.ids)
        self.assertTrue(len(deposits_reconciliation_data), 1)
        deposit_reconciliation_lines = self.env['account.reconciliation.widget'].get_move_lines_by_batch_payment(
            self.bank_statement_line.id, self.batch_inbound_usd.id)
        self.assertTrue(len(deposit_reconciliation_lines), 4)

        # Review statement line
        self.assertFalse(self.bank_statement_line.is_reconciled)
        lines_vals_list = [{'id': line['id']} for line in deposit_reconciliation_lines]
        self.env['account.reconciliation.widget'].process_bank_statement_line(self.bank_statement_line.ids,
                                                                              [{'lines_vals_list': lines_vals_list}])
        self.assertTrue(self.bank_statement_line.is_reconciled)

    def test_adjustment_lines_of_outbound_batch(self):
        self.batch_outbound_usd.validate_batch_button()

        # Check possible matching lines of batch statement in bank review screen
        deposits_reconciliation_data = self.env['account.reconciliation.widget'].get_batch_payments_data(
            self.bank_statement_payment.ids)
        self.assertTrue(len(deposits_reconciliation_data), 1)
        deposit_reconciliation_lines = self.env['account.reconciliation.widget'].get_move_lines_by_batch_payment(
            self.bank_statement_line_payment.id, self.batch_outbound_usd.id)
        self.assertTrue(len(deposit_reconciliation_lines), 4)

        # Review statement line
        self.assertFalse(self.bank_statement_line_payment.is_reconciled)
        lines_vals_list = [{'id': line['id']} for line in deposit_reconciliation_lines]
        self.env['account.reconciliation.widget'].process_bank_statement_line(self.bank_statement_line_payment.ids,
                                                                              [{'lines_vals_list': lines_vals_list}])
        self.assertTrue(self.bank_statement_line_payment.is_reconciled)
