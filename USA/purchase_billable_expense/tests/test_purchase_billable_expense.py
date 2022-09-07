from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from odoo import Command

@tagged('post_install', '-at_install', 'basic_test')
class TestUSAPurchaseBillableExpense(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.customer = cls.env['res.partner'].create({
            'name': 'Test person',
        })

        cls.po = cls.env['purchase.order'].create({
            'partner_id': cls.partner_a.id,
            'order_line': [
                Command.create({'product_id': cls.product_a.id, 'product_qty': 1, 'price_unit': 199.99}),
                Command.create({'product_id': cls.product_b.id, 'product_qty': 10, 'price_unit': 299.99})
            ]
        })

        cls.po.open_expense_popup()
        cls.expenses = cls.po.billable_expenses_ids

        currency = cls.company_data['currency']
        currency.write({'decimal_places': 2})
        cls.decimal_places = currency.decimal_places

    def test_billable_expense_lines(self):
        """
        Test data synchornization between billable expense lines and PO lines
        """
        po_lines = self.po.order_line
        expense_lines =  self.expenses
        self.assertEqual(len(po_lines),len(expense_lines))
        for po_item, expense_item in zip(po_lines, expense_lines):
            expected_result = [{
                'name': expense_item.description,
                'price_subtotal': expense_item.amount,
                'currency_id': expense_item.currency_id.id,
                'company_id': expense_item.company_id.id
            }]
            self.assertRecordValues(po_item, expected_result)

    def test_fixed_markup_amount(self):
        """
        Test fixed markup amount on billable_expense lines
        """
        expected_amount = [200, 2999.91]
        for idx, expense in enumerate(self.expenses):
            expense.amount_markup = 0.01
            self.assertAlmostEqual(expense.amount_total, expected_amount[idx], self.decimal_places)

    def test_percentage_markup_amount(self):
        """
        Test percentage markup amount on billable_expense lines
        """
        expected_amount = [299.99, 4499.85]
        for idx, expense in enumerate(self.expenses):
            expense.amount_markup_percentage = 50
            self.assertAlmostEqual(expense.amount_total,expected_amount[idx], self.decimal_places)

    def test_mixed_markup_amount(self):
        """
        Test fixed markup amount on billable_expense lines
        """
        expected_amount = [423.44, 4623.3]
        for idx, expense in enumerate(self.expenses):
            expense.amount_markup_percentage = 50
            expense.amount_markup = 123.45
            self.assertAlmostEqual(expense.amount_total, expected_amount[idx], self.decimal_places)
    def test_cancel_PO_with_billable_expenses(self):
        """
        Test cancel PO with billable expenses will remove all billable expense of this PO
        """
        for expense in self.expenses:
            expense.write({'customer_id': self.customer.id})
        self.po.button_cancel()
        self.assertEqual(len(self.po.billable_expenses_ids), 0)