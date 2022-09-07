from odoo.tests import tagged
from datetime import date
from .common import AccountTestInvoicingCommonDeposit


@tagged('post_install', '-at_install', 'basic_test')
class TestDepositJournalEntry(AccountTestInvoicingCommonDeposit):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.partner_b_bank_account = cls.env['res.partner.bank'].create({
            'acc_number': 'BE32707171912447',
            'partner_id': cls.partner_b.id,
            'acc_type': 'bank',
        })
        cls.partner_b.write({
            'bank_ids': [(6, 0, cls.partner_b_bank_account.ids)],
        })


    def test_customer_deposit_journal_entry_sync(self):
        """
        Test customer deposit and its journal entry sync when create, write
        """
        # Create new deposit in current company, currency is USD with rate = 1
        deposit_date = date(2021, 12, 1)
        customer_deposit = self.create_customer_deposit(partner_id=self.partner_a.id, amount=1000.0, date=deposit_date)

        # Check deposit, journal entry and journal item records
        expected_deposit_values = {
            'amount': 1000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'is_reconciled': False,
            'currency_id': self.company_data['currency'].id,
            'partner_id': self.partner_a.id,
            'destination_account_id': self.partner_a.property_account_receivable_id.id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
            'partner_bank_id': False,
            'date': deposit_date
        }

        expected_move_values = {
            'currency_id': self.company_data['currency'].id,
            'partner_id': self.partner_a.id,
            'partner_bank_id': False,
            'date': deposit_date
        }

        expected_liquidity_line = {
            'debit': 1000.0,
            'credit': 0.0,
            'amount_currency': 1000.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.company.account_journal_payment_debit_account_id.id,
        }

        expected_receivable_line = {
            'debit': 0.0,
            'credit': 0.0,
            'amount_currency': 0.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.company_data['default_account_receivable'].id,
        }

        expected_deposit_line = {
            'debit': 0.0,
            'credit': 1000.0,
            'amount_currency': -1000.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.partner_a.property_account_customer_deposit_id.id,
        }

        self.assertRecordValues(customer_deposit, [expected_deposit_values])
        self.assertRecordValues(customer_deposit.move_id, [expected_move_values])
        self.assertRecordValues(customer_deposit.line_ids.sorted('balance'), [
            expected_deposit_line,
            expected_receivable_line,
            expected_liquidity_line
        ])

        # Update currency_id, partner_id, amount, deposit account, date, partner bank account of deposit
        customer_deposit_account_copy = self.copy_account(self.customer_deposit_account)
        new_deposit_date = date(2021, 11, 1)
        customer_deposit.write({
            'currency_id': self.currency_data['currency'].id, # Foreign currency, rate = 2
            'partner_id': self.partner_b.id,
            'amount': 500.0,
            'partner_bank_id': self.partner_b_bank_account.id,
            'date': new_deposit_date,
            'property_account_customer_deposit_id': customer_deposit_account_copy.id,
        })

        # Check deposit, journal entry and journal item records
        self.assertRecordValues(customer_deposit, [{
            **expected_deposit_values,
            'amount': 500.0,
            'currency_id': self.currency_data['currency'].id,
            'partner_id': self.partner_b.id,
            'partner_bank_id': self.partner_b_bank_account.id,
            'destination_account_id': self.partner_b.property_account_receivable_id.id,
            'date': new_deposit_date,
            'property_account_customer_deposit_id': customer_deposit_account_copy.id,
        }])
        self.assertRecordValues(customer_deposit.move_id, [{
            **expected_move_values,
            'currency_id': self.currency_data['currency'].id,
            'partner_id': self.partner_b.id,
            'partner_bank_id': self.partner_b_bank_account.id,
            'date': new_deposit_date,
        }])
        self.assertRecordValues(customer_deposit.line_ids.sorted('balance'), [
            {
                **expected_deposit_line,
                'account_id': customer_deposit_account_copy.id,
                'debit': 0.0,
                'credit': 250.0, # USD currency
                'amount_currency': -500.0, # Foreign currency
                'currency_id': self.currency_data['currency'].id,
            },
            {
                **expected_receivable_line,
                'account_id': self.partner_b.property_account_receivable_id.id,
                'debit': 0.0,
                'credit': 0.0,
                'amount_currency': 0.0,
                'currency_id': self.currency_data['currency'].id,
            },
            {
                **expected_liquidity_line,
                'debit': 250.0, # USD currency
                'credit': 0.0,
                'amount_currency': 500.0, # Foreign currency
                'currency_id': self.currency_data['currency'].id,
            },
        ])

    def test_vendor_deposit_journal_entry_sync(self):
        """
        Test vendor deposit and its journal entry sync when create, write
        """
        # Create new deposit in current company, currency is USD with rate = 1
        deposit_date = date(2021, 12, 1)
        vendor_deposit = self.create_vendor_deposit(partner_id=self.partner_a.id, date=deposit_date, amount=1000.0)

        # Check deposit, journal entry and journal item records
        expected_deposit_values = {
            'amount': 1000.0,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'is_reconciled': False,
            'currency_id': self.company_data['currency'].id,
            'partner_id': self.partner_a.id,
            'destination_account_id': self.partner_a.property_account_payable_id.id,
            'payment_method_line_id': self.outbound_payment_method_line.id,
            'partner_bank_id': False,
            'date': deposit_date
        }

        expected_move_values = {
            'currency_id': self.company_data['currency'].id,
            'partner_id': self.partner_a.id,
            'partner_bank_id': False,
            'date': deposit_date
        }

        expected_liquidity_line = {
            'debit': 0.0,
            'credit': 1000.0,
            'amount_currency': -1000.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.company.account_journal_payment_credit_account_id.id,
        }

        expected_receivable_line = {
            'debit': 0.0,
            'credit': 0.0,
            'amount_currency': 0.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.company_data['default_account_payable'].id,
        }

        expected_deposit_line = {
            'debit': 1000.0,
            'credit': 0.0,
            'amount_currency': 1000.0,
            'currency_id': self.company_data['currency'].id,
            'account_id': self.vendor_deposit_account.id,
        }

        self.assertRecordValues(vendor_deposit, [expected_deposit_values])
        self.assertRecordValues(vendor_deposit.move_id, [expected_move_values])
        self.assertRecordValues(vendor_deposit.line_ids.sorted('balance'), [
            expected_liquidity_line,
            expected_receivable_line,
            expected_deposit_line,
        ])

        # Update currency_id, partner_id, amount, deposit account, date, partner bank account of deposit
        vendor_deposit_account_copy = self.copy_account(self.vendor_deposit_account)
        new_deposit_date = date(2021, 11, 1)
        vendor_deposit.write({
            'currency_id': self.currency_data['currency'].id, # Foreign currency, rate = 2
            'partner_id': self.partner_b.id,
            'amount': 500.0,
            'partner_bank_id': self.partner_b_bank_account.id,
            'date': new_deposit_date,
            'property_account_vendor_deposit_id': vendor_deposit_account_copy.id,
        })

        self.assertRecordValues(vendor_deposit, [{
            **expected_deposit_values,
            'amount': 500.0,
            'currency_id': self.currency_data['currency'].id,
            'partner_id': self.partner_b.id,
            'partner_bank_id': self.partner_b_bank_account.id,
            'destination_account_id': self.partner_b.property_account_payable_id.id,
            'date': new_deposit_date,
            'property_account_vendor_deposit_id': vendor_deposit_account_copy.id,
        }])
        self.assertRecordValues(vendor_deposit.move_id, [{
            **expected_move_values,
            'currency_id': self.currency_data['currency'].id,
            'partner_id': self.partner_b.id,
            'partner_bank_id': self.partner_b_bank_account.id,
            'date': new_deposit_date,
        }])

        # Check deposit, journal entry and journal item records
        self.assertRecordValues(vendor_deposit.line_ids.sorted('balance'), [
            {
                **expected_liquidity_line,
                'debit': 0.0,
                'credit': 250.0, # USD currency
                'amount_currency': -500.0, # Foreign currency
                'currency_id': self.currency_data['currency'].id,
            },
            {
                **expected_receivable_line,
                'account_id': self.partner_b.property_account_payable_id.id,
                'debit': 0.0,
                'credit': 0.0,
                'amount_currency': 0.0,
                'currency_id': self.currency_data['currency'].id,
            },
            {
                **expected_deposit_line,
                'account_id': vendor_deposit_account_copy.id,
                'debit': 250.0, # USD currency
                'credit': 0.0,
                'amount_currency': 500.0, # Foreign currency
                'currency_id': self.currency_data['currency'].id,
            },
        ])
