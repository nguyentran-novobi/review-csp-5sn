from email import message
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import Form, tagged
from odoo.exceptions import UserError
from odoo import fields

import copy


@tagged("post_install", "-at_install", "basic_test")
class TestPaymentReceipt(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super(TestPaymentReceipt, cls).setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.payment_method_line_manual =  cls.bank_journal.inbound_payment_method_line_ids[0]
        cls.payment_method_line_batch_deposit = cls.bank_journal.inbound_payment_method_line_ids[1]
        cls.income_account = cls.copy_account(cls.company_data['default_account_revenue'])
        cls.expense_account = cls.copy_account(cls.company_data['default_account_expense'])
        cls.outstanding_receivable_account = cls.env['account.account'].search([('code', '=', '101402')], limit = 1)
        cls.payment_default_data = {
            'amount': 1000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': cls.partner_a.id,
            'income_account': cls.income_account.id,
            'date': fields.Date.from_string("2022-01-01"),
            'journal_id': cls.bank_journal.id,
            'payment_method_line_id': cls.payment_method_line_manual.id,
            'is_payment_receipt': True
        }
        cls.curr_EUR = cls.env.ref("base.EUR")
        cls.curr_USD = cls.env.ref("base.USD")
        cls.company_data['currency'].write({'rounding': 0.01})
        cls.curr_EUR.write({
            'active': True,
            'rounding': 0.01
        })
        cls.env['res.currency.rate'].create([{
            'currency_id': cls.env.ref('base.EUR').id,
            'name': '2022-01-01',
            'rate': 0.71,
        }])

    def test_sync_payment_and_journal_entry(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        move_lines = payment.move_id.line_ids
        expected_move_result = {
            'date': fields.Date.from_string("2022-01-01"),
            'journal_id': self.bank_journal.id,
            'is_payment_receipt': True,
        }
        self.assertRecordValues(payment.move_id, [expected_move_result])
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.income_account.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 1000.0
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'account_id': self.outstanding_receivable_account.id,
                'partner_id': self.partner_a.id,
                'debit': 1000.0,
                'credit': 0.0
            },
        ])

    def test_sync_payment_and_journal_entry_zero_amount(self):
        payment = self.env['account.payment'].create({
            **self.payment_default_data,
            'amount': 0.0
        })
        move_lines = payment.move_id.line_ids
        self.assertEqual(len(move_lines), 2)
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.outstanding_receivable_account.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            }
        ])

    def test_sync_payment_and_journal_entry_different_account(self):
        new_receipt_account = self.copy_account(self.outstanding_receivable_account)
        self.payment_method_line_manual.payment_account_id = new_receipt_account
        payment = self.env['account.payment'].create(self.payment_default_data)
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.income_account.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 1000.0
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'account_id': new_receipt_account.id,
                'partner_id': self.partner_a.id,
                'debit': 1000.0,
                'credit': 0.0
            },
        ])

    def test_sync_payment_and_journal_entry_edit_amount(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        payment.amount = 1234.0
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'debit': 0.0,
                'credit': 1234.0
            },
            {
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'debit': 1234.0,
                'credit': 0.0
            },
        ])
    
    def test_sync_payment_and_journal_entry_edit_partner(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        payment.partner_id = self.partner_b
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'partner_id': self.partner_b.id
            },
            {
                'partner_id': self.partner_b.id
            },
            {
                'partner_id': self.partner_b.id
            },
        ])
    
    def test_sync_payment_and_journal_entry_edit_income_account(self):
        new_income_account = self.copy_account(self.income_account)
        payment = self.env['account.payment'].create(self.payment_default_data)
        payment.income_account = new_income_account
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': new_income_account.id,
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
            },
            {
                'account_id': self.outstanding_receivable_account.id,
            },
        ])

    def test_sync_payment_and_journal_entry_edit_currency(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        payment.currency_id = self.curr_EUR
        move_lines = payment.move_id.line_ids
        lines = []
        for line in move_lines:
            lines.append(line)
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'debit': 0.0,
                'credit': 1408.45
            },
            {
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'debit': 1408.45,
                'credit': 0.0
            },
        ])

    def test_change_from_payment_receipt_to_payment(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        payment.is_payment_receipt = False
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 1000.0
            },
            {
                'account_id': self.outstanding_receivable_account.id,
                'partner_id': self.partner_a.id,
                'debit': 1000.0,
                'credit': 0.0
            },
        ])
    
    def test_change_from_payment_to_payment_receipt(self):
        payment = self.env['account.payment'].create({
            **self.payment_default_data,
            'is_payment_receipt': False
        })
        payment.is_payment_receipt = True
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.income_account.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 1000.0
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'account_id': self.outstanding_receivable_account.id,
                'partner_id': self.partner_a.id,
                'debit': 1000.0,
                'credit': 0.0
            },
        ])
    
    def test_error_when_edit_move_line(self):
        payment = self.env['account.payment'].create(self.payment_default_data)
        move_lines = payment.move_id.line_ids
        try:
            move_lines.write({'partner_id': self.partner_b.id})
        except UserError(message):
            self.assertEqual(message, "Journal Items of a Payment Receipt should be updated from the payment form.")
    
    def test_sync_payment_and_journal_entry_vendor(self):
        payment_default_data_vendor = self.get_vendor_default_payment_data()
        payment = self.env['account.payment'].create(payment_default_data_vendor)
        move_lines = payment.move_id.line_ids
        expected_move_result = {
            'date': fields.Date.from_string("2022-01-01"),
            'journal_id': self.bank_journal.id,
            'is_payment_receipt': True,
        }
        self.assertRecordValues(payment.move_id, [expected_move_result])
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.expense_account.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 1000.0
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0
            },
            {
                'account_id': self.outstanding_receivable_account.id,
                'partner_id': self.partner_a.id,
                'debit': 1000.0,
                'credit': 0.0
            },
        ])
    
    def test_sync_payment_and_journal_entry_edit_expense_account(self):
        payment_default_data_vendor = self.get_vendor_default_payment_data()
        new_expense_account = self.copy_account(self.expense_account)
        payment = self.env['account.payment'].create(payment_default_data_vendor)
        move_lines = payment.move_id.line_ids
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': self.expense_account.id,
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
            },
            {
                'account_id': self.outstanding_receivable_account.id,
            },
        ])
        payment.expense_account = new_expense_account
        self.assertRecordValues(move_lines.sorted('balance'), [
            {
                'account_id': new_expense_account.id,
            },
            {
                'account_id': self.partner_a.property_account_receivable_id.id,
            },
            {
                'account_id': self.outstanding_receivable_account.id,
            },
        ])
    
    def get_vendor_default_payment_data(self):
        payment_default_data_vendor = copy.deepcopy(self.payment_default_data)
        payment_default_data_vendor.pop('income_account')
        payment_default_data_vendor.update({'expense_account': self.expense_account.id})
        return payment_default_data_vendor

