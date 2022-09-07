from odoo.tests import tagged
from .common import AccountTestInvoicingCommonDeposit
import json


@tagged('post_install', '-at_install', 'basic_test')
class TestDepositPaymentWidget(AccountTestInvoicingCommonDeposit):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Customer payments
        cls.cust_deposit_usd = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=1000.8567,
                                                           date='2021-01-01', auto_validate=True)

        cls.cust_deposit_eur = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=1000.8567,
                                                           date='2021-01-01', currency_id=cls.curr_eur.id, auto_validate=True)

        cls.cust_payment_usd = cls.create_customer_payment(partner_id=cls.partner_a.id, amount=500.456,
                                                           date='2021-01-01', auto_validate=True)

        # Vendor payments
        cls.vend_deposit_usd = cls.create_vendor_deposit(partner_id=cls.partner_a.id, amount=1000.8567,
                                                         date='2021-01-01',auto_validate=True)

        cls.vend_deposit_eur = cls.create_vendor_deposit(partner_id=cls.partner_a.id, amount=1000.8567,
                                                         date='2021-01-01', currency_id=cls.curr_eur.id, auto_validate=True)

        cls.vend_payment_usd = cls.create_vendor_payment(partner_id=cls.partner_a.id, amount=500.456,
                                                         date='2021-01-01', auto_validate=True)

    def _test_outstanding_payments_widget(self, invoice, expected_amounts):
        """ Check the outstanding payments widget before/after the reconciliation.
        :param invoice_id: An account.move record
        :param expected_amounts: A map <move_id> -> <amount>
        """
        # Check outstanding payments widget before reconciliation
        to_reconcile_payments_widget_vals = json.loads(invoice.invoice_outstanding_credits_debits_widget)

        self.assertTrue(to_reconcile_payments_widget_vals)

        current_amounts = {vals['move_id']: vals['amount'] for vals in to_reconcile_payments_widget_vals['content']}
        self.assertDictEqual(current_amounts, expected_amounts)

        # Reconcile payments and invoice
        payment_move_ids = self.env['account.move'].browse(list(current_amounts.keys()))
        self._reconcile_invoice_and_payments(invoice, payment_move_ids)

        # Check invoice payments widget after reconciliation
        reconciled_payments_widget_vals = json.loads(invoice.invoice_payments_widget)
        current_amounts = {vals['move_id']: vals['amount'] for vals in reconciled_payments_widget_vals['content']}
        self.assertEqual(sum(expected_amounts.values()), sum(current_amounts.values()))

        # Check deposit intermediate JEs
        intermediate_entries = self.env['account.move'].browse(list(current_amounts.keys())).filtered(lambda r: r.is_deposit)
        self.assertTrue(intermediate_entries)

        # Check deposit intermediate JEs when setting invoice to draft
        invoice.button_draft()
        self.assertFalse(intermediate_entries.exists())

    def test_outstanding_payments_for_customer_invoice_single_currency(self):
        """
        Test the outstanding payments widget on invoices having the same currency as the company one
        """
        # Test customer invoice USD
        out_invoice = self.create_customer_invoice(amount=5000.0, partner_id=self.partner_a.id, date='2021-01-01',
                                                   auto_validate=True)

        # Expected amounts are amounts of payments/deposits shown in Outstanding credit/debit on invoice form
        # Need to convert amount of EUR deposit to invoice currency (USD)
        expected_amounts = {
            self.cust_deposit_usd.move_id.id: 1000.86,
            self.cust_deposit_eur.move_id.id: 1215.44,
            self.cust_payment_usd.move_id.id: 500.46,
        }
        self._test_outstanding_payments_widget(out_invoice, expected_amounts)

    def test_outstanding_payments_for_vendor_bill_single_currency(self):
        """
        Test the outstanding payments widget on bills having the same currency as the company one
        """
        # Test vendor bill USD
        in_invoice = self.create_vendor_bill(amount=5000.0, partner_id=self.partner_a.id, date='2021-01-01',
                                             auto_validate=True)

        # Expected amounts are amounts of payments/deposits shown in Outstanding credit/debit on invoice form
        # Need to convert amount of EUR deposit to invoice currency (USD)
        expected_amounts = {
            self.vend_deposit_usd.move_id.id: 1000.86,
            self.vend_deposit_eur.move_id.id: 1215.44,
            self.vend_payment_usd.move_id.id: 500.46,
        }
        self._test_outstanding_payments_widget(in_invoice, expected_amounts)

    def test_outstanding_payments_for_customer_invoice_foreign_currency(self):
        """
        Test the outstanding payments widget on invoices having a foreign currency
        """
        # Test customer invoice EUR
        out_invoice = self.create_customer_invoice(date='2021-01-01', partner_id=self.partner_a.id, amount=2500.0,
                                                   currency_id=self.curr_eur.id, auto_validate=True)

        # Expected amounts are amounts of payments/deposits shown in Outstanding credit/debit on invoice form
        # Need to convert amount of USD deposit/payment to invoice currency (EUR)
        expected_amounts = {
            self.cust_deposit_usd.move_id.id: 824.16,
            self.cust_deposit_eur.move_id.id: 1000.86,
            self.cust_payment_usd.move_id.id: 412.11,
        }
        self._test_outstanding_payments_widget(out_invoice, expected_amounts)

    def test_outstanding_payments_for_vendor_bill_foreign_currency(self):
        """
        Test the outstanding payments widget on bills having a foreign currency
        """
        # Test vendor bill EUR
        in_invoice = self.create_vendor_bill(date='2021-01-01', partner_id=self.partner_a.id, amount=2500.0,
                                             currency_id=self.curr_eur.id, auto_validate=True)

        # Expected amounts are amounts of payments/deposits shown in Outstanding credit/debit on invoice form
        # Need to convert amount of USD deposit/payment to invoice currency (EUR)
        expected_amounts = {
            self.vend_deposit_usd.move_id.id: 824.16,
            self.vend_deposit_eur.move_id.id: 1000.86,
            self.vend_payment_usd.move_id.id: 412.11,
        }
        self._test_outstanding_payments_widget(in_invoice, expected_amounts)

    def test_deposit_to_payment_journal_entry_for_customer_invoice(self):
        """
        Test intermediate JE created by reconciling invoice and deposit
        """
        # ===== Test customer invoice USD =====
        out_invoice = self.create_customer_invoice(date='2021-01-01',  partner_id=self.partner_a.id, amount=2500.0,
                                                   auto_validate=True)

        payment_moves = (self.cust_deposit_usd + self.cust_deposit_eur).mapped('move_id')
        self._reconcile_invoice_and_payments(out_invoice, payment_moves)
        reconciled_payments_widget_vals = json.loads(out_invoice.invoice_payments_widget)
        move_ids = [vals['move_id'] for vals in reconciled_payments_widget_vals['content']]
        partial_ids = [vals['partial_id'] for vals in reconciled_payments_widget_vals['content']]
        intermediate_moves = self.env['account.move'].browse(move_ids)

        # Check journal items of intermediate JE
        self.assertRecordValues(intermediate_moves[0].line_ids.sorted('balance'), [
            {
                'account_id': self.receivable_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1000.86
            },
            {
                'account_id': self.customer_deposit_account.id,
                'reconciled': 1,
                'debit': 1000.86,
                'credit': 0
            }
        ])
        self.assertRecordValues(intermediate_moves[1].line_ids.sorted('balance'), [
            {
                'account_id': self.receivable_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1215.44
            },
            {
                'account_id': self.customer_deposit_account.id,
                'reconciled': 1,
                'debit': 1215.44,
                'credit': 0
            }
        ])

        # Check un-reconcile invoice and deposit
        # Intermediate JEs should be deleted
        [out_invoice.js_remove_outstanding_partial(partial_id) for partial_id in partial_ids]
        self.assertFalse(intermediate_moves.exists())

    def test_deposit_to_payment_journal_entry_for_vendor_bill(self):
        """
        Test intermediate JE created by reconciling invoice and deposit
        """
        # ===== Test vendor bill USD =====
        in_invoice = self.create_vendor_bill(date='2021-01-01',  partner_id=self.partner_a.id, amount=2500.0,
                                             auto_validate=True)

        payment_moves = (self.vend_deposit_usd + self.vend_deposit_eur).mapped('move_id')
        self._reconcile_invoice_and_payments(in_invoice, payment_moves)
        reconciled_payments_widget_vals = json.loads(in_invoice.invoice_payments_widget)
        move_ids = [vals['move_id'] for vals in reconciled_payments_widget_vals['content']]
        partial_ids = [vals['partial_id'] for vals in reconciled_payments_widget_vals['content']]
        intermediate_moves = self.env['account.move'].browse(move_ids)

        # Check journal items of intermediate JE
        self.assertRecordValues(intermediate_moves[0].line_ids.sorted('balance'), [
            {
                'account_id': self.vendor_deposit_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1000.86
            },
            {
                'account_id': self.payable_account.id,
                'reconciled': 1,
                'debit': 1000.86,
                'credit': 0
            }
        ])
        self.assertRecordValues(intermediate_moves[1].line_ids.sorted('balance'), [
            {
                'account_id': self.vendor_deposit_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1215.44
            },
            {
                'account_id': self.payable_account.id,
                'reconciled': 1,
                'debit': 1215.44,
                'credit': 0
            }
        ])

        # Check un-reconcile invoice and deposit
        # Intermediate JEs should be deleted
        [in_invoice.js_remove_outstanding_partial(partial_id) for partial_id in partial_ids]
        self.assertFalse(intermediate_moves.exists())

    def test_deposit_to_payment_journal_entry_for_customer_invoice_foreign_currency(self):
        """
        Test intermediate JE created by reconciling invoice and deposit in foreign currency
        """
        # ===== Test customer invoice EUR =====
        out_invoice = self.create_customer_invoice(date='2021-06-01', amount=1000.86, partner_id=self.partner_a.id,
                                                   currency_id=self.curr_eur.id, auto_validate=True)

        self._reconcile_invoice_and_payments(out_invoice, self.cust_deposit_eur.move_id)
        reconciled_payments_widget_vals = json.loads(out_invoice.invoice_payments_widget)
        move_ids = [vals['move_id'] for vals in reconciled_payments_widget_vals['content']]
        intermediate_moves = self.env['account.move'].browse(move_ids)

        # Check AR line of invoice
        self.assertRecordValues(out_invoice.line_ids.filtered(lambda r: r.debit > 0), [
            {
                'account_id': self.receivable_account.id,
                'reconciled': 1,
                'debit': 1181.95,
                'credit': 0,
                'amount_currency': 1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

        # Check journal items of intermediate JE
        self.assertRecordValues(intermediate_moves[0].line_ids.sorted('balance'), [
            {
                'account_id': self.receivable_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1215.44,
                'amount_currency': -1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            },
            {
                'account_id': self.customer_deposit_account.id,
                'reconciled': 1,
                'debit': 1215.44,
                'credit': 0,
                'amount_currency': 1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

        # Check deposit line of deposit
        self.assertRecordValues(self.cust_deposit_eur.line_ids.filtered(lambda r: r.credit > 0), [
            {
                'account_id': self.customer_deposit_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1215.44,
                'amount_currency': -1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

    def test_deposit_to_payment_journal_entry_for_vendor_bill_foreign_currency(self):
        """
        Test intermediate JE created by reconciling bill and deposit in foreign currency
        """
        # ===== Test vendor bill EUR =====
        in_invoice = self.create_vendor_bill(date='2021-06-01', amount=1000.86,  partner_id=self.partner_a.id,
                                             currency_id=self.curr_eur.id, auto_validate=True)

        self._reconcile_invoice_and_payments(in_invoice, self.vend_deposit_eur.move_id)
        reconciled_payments_widget_vals = json.loads(in_invoice.invoice_payments_widget)
        move_ids = [vals['move_id'] for vals in reconciled_payments_widget_vals['content']]
        intermediate_moves = self.env['account.move'].browse(move_ids)

        # Check AP line of bill
        self.assertRecordValues(in_invoice.line_ids.filtered(lambda r: r.credit > 0), [
            {
                'account_id': self.payable_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1181.95,
                'amount_currency': -1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

        # Check journal items of intermediate JE
        self.assertRecordValues(intermediate_moves[0].line_ids.sorted('balance'), [
            {
                'account_id': self.vendor_deposit_account.id,
                'reconciled': 1,
                'debit': 0,
                'credit': 1215.44,
                'amount_currency': -1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            },
            {
                'account_id': self.payable_account.id,
                'reconciled': 1,
                'debit': 1215.44,
                'credit': 0,
                'amount_currency': 1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

        # Check deposit line of deposit
        self.assertRecordValues(self.vend_deposit_eur.line_ids.filtered(lambda r: r.debit > 0), [
            {
                'account_id': self.vendor_deposit_account.id,
                'reconciled': 1,
                'debit': 1215.44,
                'credit': 0,
                'amount_currency': 1000.86,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])
