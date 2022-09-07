from odoo import Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import ValidationError
from .common import TestInvoicingCommonUSAccounting


@tagged('post_install', '-at_install', 'basic_test')
class TestApplyUnpaidInvoicesInPayment(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Set currency rates
        cls.env['res.currency.rate'].create([{
            'currency_id': cls.env.ref('base.EUR').id,
            'name': '2022-01-01',
            'rate': 0.82,
        }, {
            'currency_id': cls.env.ref('base.EUR').id,
            'name': '2022-06-01',
            'rate': 0.84,
        }])

        # Invoices
        cls.invoice_800_usd = cls.create_customer_invoice(amount=800, partner_id=cls.partner_a.id, date='2022-01-01',
                                                          auto_validate=True)

        cls.invoice_400_usd = cls.create_customer_invoice(amount=400, partner_id=cls.partner_a.id, date='2022-01-01',
                                                          auto_validate=False)

        cls.invoice_200_usd = cls.create_customer_invoice(amount=200, partner_id=cls.partner_a.id, date='2022-01-01',
                                                          auto_validate=True)

        cls.invoice_1000_eur = cls.create_customer_invoice(amount=1000, partner_id=cls.partner_a.id, date='2022-01-01',
                                                           currency_id=cls.curr_eur.id, auto_validate=True)

        cls.invoice_600_eur = cls.create_customer_invoice(amount=600, partner_id=cls.partner_a.id, date='2022-06-01',
                                                          currency_id=cls.curr_eur.id, auto_validate=True)

        # Journal entries
        cls.entry_300_usd = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2022-01-01',
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data['default_account_revenue'].id,
                    'partner_id': cls.partner_a.id,
                    'debit': 0,
                    'credit': 300
                }),
                Command.create({
                    'account_id': cls.company_data['default_account_receivable'].id,
                    'partner_id': cls.partner_a.id,
                    'debit': 300,
                    'credit': 0
                }),
            ],
            'company_id': cls.company.id
        })
        cls.entry_300_usd.action_post()

        # Customer payments
        cls.payment_1000 = cls.create_customer_payment(partner_id=cls.partner_a.id, amount=1000, date='2022-01-01',
                                                       auto_validate=False)

        cls.payment_500 = cls.create_customer_payment(partner_id=cls.partner_a.id, amount=500, date='2022-01-01',
                                                      auto_validate=True)

        cls.payment_2000_eur = cls.create_customer_payment(partner_id=cls.partner_a.id, amount=2000, date='2022-01-01',
                                                           currency_id=cls.curr_eur.id, auto_validate=False)

        # Available transaction lines
        cls.transaction_lines = (cls.invoice_800_usd + cls.invoice_200_usd + cls.entry_300_usd)\
            .mapped('line_ids').filtered(lambda r: r.debit)

    def test_available_move_lines_to_be_applied_with_payment(self):
        self.assertEqual(self.payment_1000.available_move_line_ids, self.transaction_lines)

        # Add invoice $800 to payment, then check available move lines
        payment_form = Form(self.payment_1000)
        with payment_form.payment_line_ids.new() as trans_line:
            trans_line.account_move_line_id = self.invoice_800_usd.line_ids.filtered(lambda r: r.debit)
        payment_form.save()
        expected_move_lines = (self.invoice_200_usd + self.entry_300_usd).mapped('line_ids').filtered(lambda r: r.debit)
        self.assertEqual(self.payment_1000.available_move_line_ids, expected_move_lines)

        # Apply invoice $200 with payment $500, then check available move lines of payment $1000
        self._reconcile_invoice_and_payments(self.invoice_200_usd, self.payment_500)
        expected_move_lines = self.entry_300_usd.mapped('line_ids').filtered(lambda r: r.debit)
        self.assertEqual(self.payment_1000.available_move_line_ids, expected_move_lines)

    def test_added_transactions_when_onchange_partner(self):
        payment_form = Form(self.payment_1000)
        with payment_form.payment_line_ids.new() as trans_line:
            trans_line.account_move_line_id = self.invoice_800_usd.line_ids.filtered(lambda r: r.debit)
        payment_form.save()
        self.assertTrue(self.payment_1000.payment_line_ids)

        # Change partner
        payment_form.partner_id = self.partner_b
        payment_form.save()
        self.assertFalse(self.payment_1000.payment_line_ids)

    def test_added_transactions_when_onchange_payment_type(self):
        payment_form = Form(self.payment_1000)
        with payment_form.payment_line_ids.new() as trans_line:
            trans_line.account_move_line_id = self.invoice_800_usd.line_ids.filtered(lambda r: r.debit)
        payment_form.save()
        self.assertTrue(self.payment_1000.payment_line_ids)

        # Change payment type
        payment_form.payment_type = 'outbound'
        payment_form.save()
        self.assertFalse(self.payment_1000.payment_line_ids)

    def test_added_transactions_when_onchange_currency(self):
        payment_form = Form(self.payment_1000)
        with payment_form.payment_line_ids.new() as trans_line:
            trans_line.account_move_line_id = self.invoice_800_usd.line_ids.filtered(lambda r: r.debit)
        payment_form.save()
        self.assertTrue(self.payment_1000.payment_line_ids)

        # Change currency
        payment_form.currency_id = self.curr_eur
        payment_form.save()
        self.assertFalse(self.payment_1000.payment_line_ids)

    def test_onchange_payment_amount_in_added_transactions(self):
        # Reconcile invoice $800 and payment $500 => Invoice residual amount = $300
        self._reconcile_invoice_and_payments(self.invoice_800_usd, self.payment_500)

        # Add invoice $800 to payment
        payment_form = Form(self.payment_1000)
        with payment_form.payment_line_ids.new() as trans_line:
            trans_line.account_move_line_id = self.invoice_800_usd.line_ids.filtered(lambda r: r.debit)
        payment_form.save()

        # Check payment amount in added invoice
        self.assertEqual(self.payment_1000.payment_line_ids[0].payment, 300)

        # Change payment amount to negative value
        with self.assertRaises(ValidationError):
            with payment_form.payment_line_ids.edit(0) as trans_line:
                trans_line.payment = -1

        # Change payment amount to be greater than invoice residual amount
        with payment_form.payment_line_ids.edit(0) as trans_line:
            trans_line.payment = 300.01
        payment_form.save()

        self.assertEqual(self.payment_1000.payment_line_ids[0].payment, 300)

    def test_post_payment_with_added_transactions(self):
        # Add unpaid transactions to payment
        payment_form = Form(self.payment_1000)
        for transaction in self.transaction_lines:
            with payment_form.payment_line_ids.new() as trans_line:
                trans_line.account_move_line_id = transaction

        # Pay only $400 for invoice $800
        with payment_form.payment_line_ids.edit(0) as trans_line:
            trans_line.payment = 400

        payment_form.save()

        self.assertRecordValues(self.payment_1000, [{
            'to_apply_amount': 900,
            'writeoff_amount': 0,
            'outstanding_payment': 1000
        }])

        self.payment_1000.action_post()

        self.assertRecordValues(self.payment_1000, [{
            'applied_amount': 900,
            'writeoff_amount': 0,
            'outstanding_payment': 100
        }])

        self.assertRecordValues(self.transaction_lines, [{
            'balance': 800,
            'amount_residual': 400
        }, {
            'balance': 200,
            'amount_residual': 0
        }, {
            'balance': 300,
            'amount_residual': 0
        }])

    def test_post_payment_having_writeoff_with_added_transactions(self):
        # Create payment with write-off line
        writeoff_vals = {
            'account_id': self.company_data['default_account_assets'].id,
            'amount': 300
        }
        payment = self.create_payment(partner_id=self.partner_a.id, amount=700, date='2022-01-01',
                                      auto_validate=False, write_off_line_vals=writeoff_vals)

        # Add unpaid transaction to payment, then post it
        payment_form = Form(payment)
        for transaction in self.transaction_lines:
            with payment_form.payment_line_ids.new() as trans_line:
                trans_line.account_move_line_id = transaction

        payment_form.save()

        self.assertRecordValues(payment, [{
            'to_apply_amount': 1300,
            'applied_amount': 0,
            'writeoff_amount': 300,
            'outstanding_payment': 1000,
            'amount': 700
        }])

        with self.assertRaises(ValidationError):
            # Raise error because to-apply amount > payment amount
            payment.action_post()

        # Change to-apply amount of invoice $800 to $300 and post payment again
        with payment_form.payment_line_ids.edit(0) as trans_line:
            trans_line.payment = 200

        payment_form.save()
        payment.action_post()

        self.assertRecordValues(payment, [{
            'to_apply_amount': 0,
            'applied_amount': 700,
            'writeoff_amount': 300,
            'outstanding_payment': 300,
            'amount': 700
        }])

        # Set payment to draft and check payment_line_ids
        payment.action_draft()
        self.assertFalse(payment.payment_line_ids)

    def test_post_payment_with_added_transactions_foreign_currency(self):
        transaction_lines = (self.invoice_600_eur + self.invoice_1000_eur).mapped('line_ids').filtered(lambda r: r.debit)
        payment_form = Form(self.payment_2000_eur)
        for transaction in transaction_lines:
            with payment_form.payment_line_ids.new() as trans_line:
                trans_line.account_move_line_id = transaction
        payment_form.save()

        self.assertRecordValues(self.payment_2000_eur, [{
            'to_apply_amount': 1600,
            'applied_amount': 0,
            'writeoff_amount': 0,
            'outstanding_payment': 2000,
            'amount': 2000
        }])

        self.payment_2000_eur.action_post()

        self.assertRecordValues(self.payment_2000_eur, [{
            'to_apply_amount': 0,
            'applied_amount': 1600,
            'writeoff_amount': 0,
            'outstanding_payment': 400,
            'amount': 2000
        }])

        self.assertRecordValues(self.payment_2000_eur.line_ids.filtered(lambda r: r.credit), [{
            'balance': -2439.02,
            'amount_residual': -505.22
        }])

        self.assertRecordValues(transaction_lines, [{
            'balance': 714.29,
            'amount_residual': 0
        }, {
            'balance': 1219.51,
            'amount_residual': 0
        }])
