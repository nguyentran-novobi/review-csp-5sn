from freezegun import freeze_time
from odoo.tests import Form, tagged
from odoo.exceptions import ValidationError
from .common import TestSaleDepositCommon


@tagged('post_install', '-at_install', 'basic_test')
class TestMakeADepositFromSalesOrder(TestSaleDepositCommon):

    def test_negative_amount_in_make_a_deposit_popup_fixed_amount(self):
        # Check when deposit_option is fixed
        self.make_a_deposit_wiz.amount = -1
        with self.assertRaises(ValidationError):
            self.make_a_deposit_wiz.action_create_deposit()

    def test_negative_amount_in_make_a_deposit_popup_percentage(self):
        # Check when deposit_option is percentage
        self.make_a_deposit_wiz.update({
            'deposit_option': 'percentage',
            'percentage': -1
        })
        with self.assertRaises(ValidationError):
            self.make_a_deposit_wiz.action_create_deposit()

    def test_deposit_created_by_make_a_deposit_popup_with_fixed_amount(self):
        self.make_a_deposit_wiz.amount = 250
        act_window = self.make_a_deposit_wiz.action_create_deposit()
        wiz_context = act_window['context']

        deposit = self.env['account.payment'].with_context(wiz_context).create({})
        deposit.action_post()

        # Check new deposit
        self.assertRecordValues(deposit, [{
            'partner_id': self.partner_a.id,
            'amount': 250,
            'currency_id': self.sale_order.currency_id.id,
            'sale_deposit_id': self.sale_order.id
        }])

    def test_deposit_created_by_make_a_deposit_popup_with_percentage(self):
        self.make_a_deposit_wiz.update({
            'deposit_option': 'percentage',
            'percentage': 15,
        })
        act_window = self.make_a_deposit_wiz.action_create_deposit()
        wiz_context = act_window['context']

        deposit = self.env['account.payment'].with_context(wiz_context).create({})
        deposit.action_post()

        # Check new deposit
        self.assertRecordValues(deposit, [{
            'partner_id': self.partner_a.id,
            'amount': 75.1,
            'currency_id': self.sale_order.currency_id.id,
            'sale_deposit_id': self.sale_order.id
        }])

    def test_deposits_of_so_with_company_currency(self):
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50.6, date='2021-01-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=15.2, date='2021-06-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)

        self.assertRecordValues(self.sale_order, [{
            'deposit_count': 3,
            'deposit_total': 329.4,
            'remaining_total': 171.24
        }])

    def test_deposits_of_so_with_foreign_currency(self):
        self.sale_order.pricelist_id = self.pricelist_eur.id
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50.6, date='2021-01-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=15.2, date='2021-06-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)

        self.assertRecordValues(self.sale_order, [{
            'deposit_count': 3,
            'deposit_total': 304.54,
            'remaining_total': 196.1
        }])

    def test_deposit_amount_exceed_so_amount_with_company_currency(self):
        # Deposit 1: 250 USD
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)
        # Deposit 2: 50 EUR -> 60.72 USD
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50, date='2021-01-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)
        # Deposit 3: 50 EUR -> 59.05 USD
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50, date='2021-06-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)
        # Deposit 4: 130.88 USD
        draft_deposit = self.create_customer_deposit(partner_id=self.partner_a.id, amount=130.88, date='2021-01-01',
                                                     auto_validate=False, sale_deposit_id=self.sale_order.id)
        self.assertRecordValues(self.sale_order, [{
            'deposit_count': 3,
            'deposit_total': 369.77,
            'remaining_total': 130.87
        }])

        with self.assertRaises(ValidationError):
            draft_deposit.action_post()

    def test_deposit_amount_exceed_so_amount_with_foreign_currency(self):
        self.sale_order.pricelist_id = self.pricelist_eur.id
        # Deposit 1: 250 EUR
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                     currency_id=self.curr_eur.id, auto_validate=True, sale_deposit_id=self.sale_order.id)
        # Deposit 2: 50 USD -> 41.17 EUR
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50, date='2021-01-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)
        # Deposit 3: 50 USD -> 42.34 EUR
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=50, date='2021-06-01', auto_validate=True,
                                     sale_deposit_id=self.sale_order.id)
        # Deposit 4: 202.97 USD -> 167.14 EUR
        draft_deposit = self.create_customer_deposit(partner_id=self.partner_a.id, amount=202.97, date='2021-01-01',
                                                     auto_validate=False, sale_deposit_id=self.sale_order.id)
        self.assertRecordValues(self.sale_order, [{
            'deposit_count': 3,
            'deposit_total': 333.51,
            'remaining_total': 167.13
        }])

        with self.assertRaises(ValidationError):
            draft_deposit.action_post()

    def test_invoice_and_deposits_reconciling_with_so_in_company_currency(self):
        """
        Test invoice of SO is reconciled with deposits automatically when posting it
        SO currency is company currency
        """
        # Deposit 1: 250 USD
        deposit_1 = self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                                 auto_validate=True, sale_deposit_id=self.sale_order.id)
        # Deposit 2: 100 USD
        deposit_2 = self.create_customer_deposit(partner_id=self.partner_a.id, amount=100, date='2021-01-01',
                                                 auto_validate=True, sale_deposit_id=self.sale_order.id)

        # Create invoice for SO
        self.sale_order.order_line.qty_delivered = 1
        invoice = self.sale_order._create_invoices()
        invoice.action_post()

        # Check amount residual of invoice and deposits
        self.assertRecordValues(invoice.line_ids.filtered(lambda r: r.debit > 0), [
            {
                'debit': 500.64,
                'credit': 0,
                'amount_currency': 500.64,
                'amount_residual': 150.64,
                'amount_residual_currency': 150.64
            }
        ])
        self.assertRecordValues(deposit_1.line_ids.filtered(lambda r: r.credit > 0), [
            {
                'debit': 0,
                'credit': 250,
                'amount_currency': -250,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])
        self.assertRecordValues(deposit_2.line_ids.filtered(lambda r: r.credit > 0), [
            {
                'debit': 0,
                'credit': 100,
                'amount_currency': -100,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

    def test_invoice_and_deposits_reconciling_with_so_in_foreign_currency(self):
        """
        Test invoice of SO is reconciled with deposits automatically when posting it
        SO currency is foreign currency
        """
        self.sale_order.pricelist_id = self.pricelist_eur.id

        # Deposit 1: 250 EUR
        deposit_1 = self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                                 currency_id=self.curr_eur.id, auto_validate=True,
                                                 sale_deposit_id=self.sale_order.id)
        # Deposit 2: 250.64 EUR
        deposit_2 = self.create_customer_deposit(partner_id=self.partner_a.id, amount=250.64, date='2021-01-01',
                                                 currency_id=self.curr_eur.id, auto_validate=True,
                                                 sale_deposit_id=self.sale_order.id)

        # Create invoice for SO
        self.sale_order.order_line.qty_delivered = 1
        with freeze_time('2021-01-01'):
            # Get currency rate at 2021-1-1
            invoice = self.sale_order._create_invoices()
            invoice.action_post()

            # Check amount residual of invoice and deposits
            self.assertRecordValues(invoice.line_ids.filtered(lambda r: r.debit > 0), [
                {
                    'debit': 607.97,
                    'credit': 0,
                    'amount_currency': 500.64,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])
            self.assertRecordValues(deposit_1.line_ids.filtered(lambda r: r.credit > 0), [
                {
                    'debit': 0,
                    'credit': 303.6,
                    'amount_currency': -250,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])
            self.assertRecordValues(deposit_2.line_ids.filtered(lambda r: r.credit > 0), [
                {
                    'debit': 0,
                    'credit': 304.38,
                    'amount_currency': -250.64,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])

    def test_cancel_so_having_deposits(self):
        """
        Test cancel so having deposits will not remove links to deposits on SO
        """
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                     auto_validate=True, sale_deposit_id=self.sale_order.id)
        self.create_customer_deposit(partner_id=self.partner_a.id, amount=100, date='2021-01-01',
                                     auto_validate=True, sale_deposit_id=self.sale_order.id)

        self.assertTrue(self.sale_order.deposit_ids)
        self.sale_order.action_cancel()
        self.assertTrue(self.sale_order.deposit_ids)

    def test_set_to_draft_deposit_linked_to_so(self):
        """
        Test set to draft deposit will not remove link to SO on deposit
        """
        deposit = self.create_customer_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                               auto_validate=True, sale_deposit_id=self.sale_order.id)

        self.assertTrue(deposit.sale_deposit_id)
        deposit.action_draft()
        self.assertTrue(deposit.sale_deposit_id)
