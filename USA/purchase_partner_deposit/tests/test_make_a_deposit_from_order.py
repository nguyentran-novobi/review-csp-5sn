from freezegun import freeze_time
from odoo import Command
from odoo.tests import Form, tagged
from odoo.exceptions import ValidationError
from odoo.addons.account_partner_deposit.tests.common import AccountTestInvoicingCommonDeposit


@tagged('post_install', '-at_install', 'basic_test')
class TestMakeADepositFromPurchaseOrder(AccountTestInvoicingCommonDeposit):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        
        # Create PO
        purchase_order_model = cls.env['purchase.order'].with_context(tracking_disable=True)
        cls.product_a.type = 'service'
        cls.purchase_order = purchase_order_model.create({
            'partner_id': cls.partner_a.id,
            'order_line': [
                Command.create({
                    'name': cls.product_a.name,
                    'product_id': cls.product_a.id,
                    'product_qty': 1,
                    'product_uom': cls.product_a.uom_id.id,
                    'price_unit': 500.64,
                    'taxes_id': False,
                })
            ]
        })
        cls.purchase_order.button_confirm()

        # Create Make a deposit wizard
        context = {
            'active_model': 'purchase.order',
            'active_id': cls.purchase_order.id,
            'default_currency_id': cls.purchase_order.currency_id.id
        }
        cls.make_a_deposit_wiz = cls.env['order.make.deposit'].with_context(context).create({})

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
            'currency_id': self.purchase_order.currency_id.id,
            'purchase_deposit_id': self.purchase_order.id
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
            'currency_id': self.purchase_order.currency_id.id,
            'purchase_deposit_id': self.purchase_order.id
        }])

    def test_deposits_of_po_with_company_currency(self):
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50.6, date='2021-01-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=15.2, date='2021-06-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)

        self.assertRecordValues(self.purchase_order, [{
            'deposit_count': 3,
            'deposit_total': 329.4,
            'remaining_total': 171.24
        }])

    def test_deposits_of_po_with_foreign_currency(self):
        self.purchase_order.currency_id = self.curr_eur.id
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50.6, date='2021-01-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=15.2, date='2021-06-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)

        self.assertRecordValues(self.purchase_order, [{
            'deposit_count': 3,
            'deposit_total': 304.54,
            'remaining_total': 196.1
        }])

    def test_deposit_amount_exceed_po_amount_with_company_currency(self):
        # Deposit 1: 250 USD
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)
        # Deposit 2: 50 EUR -> 60.72 USD
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50, date='2021-01-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        # Deposit 3: 50 EUR -> 59.05 USD
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50, date='2021-06-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        # Deposit 4: 130.88 USD
        draft_deposit = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=130.88, date='2021-01-01',
                                                   auto_validate=False, purchase_deposit_id=self.purchase_order.id)
        self.assertRecordValues(self.purchase_order, [{
            'deposit_count': 3,
            'deposit_total': 369.77,
            'remaining_total': 130.87
        }])

        with self.assertRaises(ValidationError):
            draft_deposit.action_post()

    def test_deposit_amount_exceed_po_amount_with_foreign_currency(self):
        self.purchase_order.currency_id = self.curr_eur.id
        # Deposit 1: 250 EUR
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                   currency_id=self.curr_eur.id, auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        # Deposit 2: 50 USD -> 41.17 EUR
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50, date='2021-01-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)
        # Deposit 3: 50 USD -> 42.34 EUR
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=50, date='2021-06-01', auto_validate=True,
                                   purchase_deposit_id=self.purchase_order.id)
        # Deposit 4: 202.97 USD -> 167.14 EUR
        draft_deposit = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=202.97, date='2021-01-01',
                                                   auto_validate=False, purchase_deposit_id=self.purchase_order.id)
        self.assertRecordValues(self.purchase_order, [{
            'deposit_count': 3,
            'deposit_total': 333.51,
            'remaining_total': 167.13
        }])

        with self.assertRaises(ValidationError):
            draft_deposit.action_post()

    def test_bill_and_deposits_reconciling_with_po_in_company_currency(self):
        """
        Test bill of PO is reconciled with deposits automatically when posting it
        PO currency is company currency
        """
        # Deposit 1: 250 USD
        deposit_1 = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                               auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        # Deposit 2: 100 USD
        deposit_2 = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=100, date='2021-01-01',
                                               auto_validate=True, purchase_deposit_id=self.purchase_order.id)

        # Create bill for PO
        self.purchase_order.order_line.qty_received = 1
        self.purchase_order.action_create_invoice()
        bill = self.purchase_order.invoice_ids
        bill.invoice_date = '2021-01-01'
        bill.action_post()

        # Check amount residual of bill and deposits
        self.assertRecordValues(bill.line_ids.filtered(lambda r: r.credit > 0), [
            {
                'debit': 0,
                'credit': 500.64,
                'amount_currency': -500.64,
                'amount_residual': -150.64,
                'amount_residual_currency': -150.64
            }
        ])
        self.assertRecordValues(deposit_1.line_ids.filtered(lambda r: r.debit > 0), [
            {
                'debit': 250,
                'credit': 0,
                'amount_currency': 250,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])
        self.assertRecordValues(deposit_2.line_ids.filtered(lambda r: r.debit > 0), [
            {
                'debit': 100,
                'credit': 0,
                'amount_currency': 100,
                'amount_residual': 0,
                'amount_residual_currency': 0
            }
        ])

    def test_bill_and_deposits_reconciling_with_po_in_foreign_currency(self):
        """
        Test bill of PO is reconciled with deposits automatically when posting it
        PO currency is foreign currency
        """
        self.purchase_order.currency_id = self.curr_eur.id

        # Deposit 1: 250 EUR
        deposit_1 = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                               currency_id=self.curr_eur.id, auto_validate=True,
                                               purchase_deposit_id=self.purchase_order.id)
        # Deposit 2: 250.64 EUR
        deposit_2 = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250.64, date='2021-01-01',
                                               currency_id=self.curr_eur.id, auto_validate=True,
                                               purchase_deposit_id=self.purchase_order.id)

        # Create bill for PO
        self.purchase_order.order_line.qty_received = 1
        with freeze_time('2021-01-01'):
            # Get currency rate at 2021-1-1
            self.purchase_order.action_create_invoice()
            bill = self.purchase_order.invoice_ids
            bill.invoice_date = '2021-01-01'
            bill.action_post()

            # Check amount residual of bill and deposits
            self.assertRecordValues(bill.line_ids.filtered(lambda r: r.credit > 0), [
                {
                    'debit': 0,
                    'credit': 607.97,
                    'amount_currency': -500.64,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])
            self.assertRecordValues(deposit_1.line_ids.filtered(lambda r: r.debit > 0), [
                {
                    'debit': 303.6,
                    'credit': 0,
                    'amount_currency': 250,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])
            self.assertRecordValues(deposit_2.line_ids.filtered(lambda r: r.debit > 0), [
                {
                    'debit': 304.38,
                    'credit': 0,
                    'amount_currency': 250.64,
                    'amount_residual': 0,
                    'amount_residual_currency': 0
                }
            ])

    def test_cancel_po_having_deposits(self):
        """
        Test cancel PO having deposits will not remove links to deposits on PO
        """
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                   auto_validate=True, purchase_deposit_id=self.purchase_order.id)
        self.create_vendor_deposit(partner_id=self.partner_a.id, amount=100, date='2021-01-01',
                                   auto_validate=True, purchase_deposit_id=self.purchase_order.id)

        self.assertTrue(self.purchase_order.deposit_ids)
        self.purchase_order.button_cancel()
        self.assertTrue(self.purchase_order.deposit_ids)

    def test_set_to_draft_deposit_linked_to_po(self):
        """
        Test set to draft deposit will not remove link to PO on deposit
        """
        deposit = self.create_vendor_deposit(partner_id=self.partner_a.id, amount=250, date='2021-01-01',
                                             auto_validate=True, purchase_deposit_id=self.purchase_order.id)

        self.assertTrue(deposit.purchase_deposit_id)
        deposit.action_draft()
        self.assertTrue(deposit.purchase_deposit_id)
