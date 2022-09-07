from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from odoo import fields, Command

@tagged('post_install', '-at_install', 'basic_test')
class TestUSABillableExpense(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super(TestUSABillableExpense, cls).setUpClass()

        cls.customer = cls.env['res.partner'].create({
            'name': 'Test person',
        })

        cls.bill = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.customer.id,
            'date': fields.Date.from_string('2021-12-12'),
            'invoice_date': fields.Date.from_string('2021-12-12'),
            'invoice_line_ids': [
                Command.create({'name': '/', 'price_unit': 12345.678}),
                Command.create({'name': '/', 'price_unit': 345})
                ],
        })

        cls.bill.action_post()
        cls.bill.open_expense_popup()
        cls.expenses = cls.bill.billable_expenses_ids

        cls.invoice = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'date': fields.Date.from_string('2021-12-12'),
            'invoice_date': fields.Date.from_string('2021-12-12'),
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 12345.678})],
        })

        currency = cls.company_data['currency']
        currency.write({'decimal_places': 2})
        cls.decimal_places = currency.decimal_places

    def test_billable_expense_lines(self):
        """
        Test data synchornization between billable expense lines and bill lines
        """
        self.bill.open_expense_popup()
        bill_lines = self.bill.invoice_line_ids
        expense_lines = self.env['billable.expenses'].search([('bill_id', '=', self.bill.id)])
        self.assertEqual(len(bill_lines),len(expense_lines))
        for bill_item, expense_item in zip(bill_lines, expense_lines):
            expected_result = [{
                'name': expense_item.description,
                'price_subtotal': expense_item.amount,
                'currency_id': expense_item.currency_id.id,
                'company_id': expense_item.company_id.id
            }]
            self.assertRecordValues(bill_item, expected_result)


    def test_fixed_markup_amount(self):
        """
        Test fixed markup amount on billable_expense lines
        """
        expected_amount = [12346.0, 345.32]
        for idx, expense in enumerate(self.expenses):
            expense.amount_markup = 0.322
            self.assertAlmostEqual(expense.amount_total, expected_amount[idx], self.decimal_places)
    
    def test_percentage_markup_amount(self):
        """
        Test percentage markup amount on billable_expense lines
        """
        expected_amount = 0.00
        for expense in self.expenses:
            expense.amount_markup_percentage = -100
            self.assertAlmostEqual(expense.amount_total, expected_amount, self.decimal_places)

    def test_mixed_markup_amount(self):
        """
        Test fixed and percentage markup amount on billable_expense lines
        """
        expected_amount = [13975.63, 390.86]
        for idx, expense in enumerate(self.expenses):
            expense.amount_markup_percentage = 13.2
            expense.amount_markup = 0.322
            self.assertAlmostEqual(expense.amount_total, expected_amount[idx], self.decimal_places)

    def test_set_to_draft_bill_with_billable_expenses(self):
        """
        Test set bill with billable expenses to draft
        """
        self.expenses.write({'customer_id': self.customer.id})
        self.bill.button_draft()
        self.assertEqual(len(self.bill.billable_expenses_ids), 0)

    def test_expense_button_name(self):
        """
        Test expense button name when 2 expenses are not yet assigned to invoice
        """
        self.expenses.write({'customer_id': self.customer.id})
        self.invoice.write({'partner_id': self.customer.id})
        self.assertEqual(self.invoice.expense_btn_name, '2 billable expense(s) can be added')

    def test_assigned_as_item_expense_button_name(self):
        """
        Test expense button name when assign 1 of 2 billable expense to invoice as item
        """
        expenses_ids = self.expenses.ids
        self.expenses.write({'customer_id': self.customer.id})
        self.invoice.write({'partner_id': self.customer.id})
        res = self.invoice.from_expense_to_invoice(expenses_ids[0:1], 'item')
        self.assertTrue(res)
        self.assertEqual(self.invoice.expense_btn_name, '1 of 2 billable expense(s) added')
        self.assertEqual(len(self.invoice.invoice_line_ids), 2)

    def test_assigned_as_one_line_expense_button_name(self):
        """
        Test expense button name when assign all 2 billable expenses to invoice as one line
        """
        expenses_ids = self.expenses.ids
        total_amount = 0
        self.expenses.write({'customer_id': self.customer.id})
        for expense in self.expenses:
            total_amount += expense.amount_currency
        self.invoice.write({'partner_id': self.customer.id})
        res = self.invoice.from_expense_to_invoice(expenses_ids, 'one')
        self.assertTrue(res)
        self.assertEqual(self.invoice.expense_btn_name, '2 of 2 billable expense(s) added')
        self.assertAlmostEqual(self.invoice.invoice_line_ids[1].price_subtotal, total_amount, self.decimal_places)