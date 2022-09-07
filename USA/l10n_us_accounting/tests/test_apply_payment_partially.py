# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import json

from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

@tagged('post_install', '-at_install', 'basic_test')
class TestApplyPaymentPartially(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company = cls.company_data['company']
        cls.company.currency_id = cls.env.ref('base.EUR')
        cls.company.currency_id = cls.env.ref('base.USD')

        cls.receivable_account = cls.company_data['default_account_receivable']
        cls.payable_account = cls.company_data['default_account_payable']

        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_euro = cls.env.ref("base.EUR")

        cls.env['res.currency.rate'].create([{
            'currency_id': cls.env.ref('base.EUR').id,
            'name': '2022-01-01',
            'rate': 0.82,
        }, {
            'currency_id': cls.env.ref('base.EUR').id,
            'name': '2022-06-01',
            'rate': 0.84,
        }])
        # ------------------ TO REMOVE ------------------------------
        cls.payment_01_2022 = cls.env['account.move'].create({
            'date': '2022-01-01',
            'line_ids': [
                Command.create({'debit': 0.0, 'credit': 500.0, 'amount_currency': -500.0, 'currency_id': cls.currency_usd.id,
                                'account_id': cls.receivable_account.id, 'partner_id': cls.partner_a.id}),
                Command.create({'debit': 500.0, 'credit': 0.0, 'amount_currency': 500.0, 'currency_id': cls.currency_usd.id,
                                'account_id': cls.payable_account.id, 'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_01_2022.action_post()

        cls.payment_02_2022 = cls.env['account.move'].create({
            'date': '2022-06-01',
            'line_ids': [
                Command.create({'debit': 0.0, 'credit': 500.0, 'amount_currency': -420.0, 'currency_id': cls.currency_euro.id,
                                'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                Command.create({'debit': 500.0, 'credit': 0.0, 'amount_currency': 420.0, 'currency_id': cls.currency_euro.id,
                                'account_id': cls.payable_account.id, 'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_02_2022.action_post()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _test_all_outstanding_payments(self, invoice, expected_amounts, full=False):
        ''' Check the outstanding payments widget before/after the reconciliation.
        :param invoice:             An account.move record.
        :param expected_amounts:    A map <move_id> -> <amount>
        :param full:                Apply payment partially or fullly
        '''

        # Check suggested outstanding payments.
        to_reconcile_payments_widget_vals = json.loads(invoice.invoice_outstanding_credits_debits_widget)
        self.assertTrue(to_reconcile_payments_widget_vals)

        current_amounts = {vals['move_id']: vals['amount']
                           for vals in to_reconcile_payments_widget_vals['content']}
        self.assertDictEqual(current_amounts, expected_amounts)


        invoice_partial_payment_env = self.env['account.invoice.partial.payment']
        for vals in to_reconcile_payments_widget_vals['content']:
            default_payment_amount = vals['amount']
            invoice_partial_payment = invoice_partial_payment_env.with_context(
                invoice_id=invoice.id,
                credit_aml_id= vals['id']
            ).create({'amount': default_payment_amount})

            with self.assertRaises(UserError):
                if invoice_partial_payment.have_same_currency:
                    invoice_partial_payment.amount = -10.0
                    invoice_partial_payment.apply()
                else:
                    # Bypass case if have_same_currency != False
                    raise UserError("Diff Currency")

            with self.assertRaises(UserError):
                if invoice_partial_payment.have_same_currency:
                    invoice_partial_payment.amount = default_payment_amount + 0.1
                    invoice_partial_payment.apply()
                else:
                    # Bypass case if have_same_currency != False
                    raise UserError("Diff Currency")
            invoice_partial_payment.apply()
        # Check payments after reconciliation.
        reconciled_payments_widget_vals = json.loads(invoice.invoice_payments_widget)

        self.assertTrue(reconciled_payments_widget_vals)

        current_amounts = {vals['move_id']: vals['amount']
                           for vals in reconciled_payments_widget_vals['content']}
        self.assertDictEqual(current_amounts, expected_amounts)

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------

    def test_outstanding_payments_single_currency(self):
        ''' Test the outstanding payments widget on invoices having the same currency
        as the company one.
        '''

        out_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2022-01-01',
            'invoice_date': '2022-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.currency_usd.id,
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 1000.0})],
        })
        out_invoice.action_post()

        in_invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2022-01-01',
            'invoice_date': '2022-06-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.currency_usd.id,
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 1000.0})],
        })
        in_invoice.action_post()

        expected_amounts = {
            self.payment_01_2022.id: 500.0,
            self.payment_02_2022.id: 500.0,
        }

        self._test_all_outstanding_payments(out_invoice, expected_amounts)
        self._test_all_outstanding_payments(in_invoice, expected_amounts)


    def test_outstanding_payments_foreign_currency(self):
        ''' Test the outstanding payments widget on invoices having a foreign currency. '''

        out_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2022-01-01',
            'invoice_date': '2022-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.currency_euro.id,
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 1111.00})],
        })
        out_invoice.action_post()

        in_invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2022-06-01',
            'invoice_date': '2022-06-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.currency_euro.id,
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 1111.00})],
        })
        in_invoice.action_post()

        expected_amounts = {
            self.payment_01_2022.id: 410.0,
            self.payment_02_2022.id: 420.0,
        }
        self._test_all_outstanding_payments(out_invoice, expected_amounts)
        self._test_all_outstanding_payments(in_invoice, expected_amounts)
