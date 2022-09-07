from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo import fields, Command

@tagged('post_install', '-at_install', 'basic_test')
class TestUSABillableExpenseCancel(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super(TestUSABillableExpenseCancel, cls).setUpClass()

        cls.customer = cls.env['res.partner'].create({
            'name': 'Test person',
        })

        cls.bill = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.customer.id,
            'date': fields.Date.from_string('2021-12-14'),
            'invoice_date': fields.Date.from_string('2021-12-14'),
            'invoice_line_ids': [
                Command.create({'name': '/', 'price_unit': 12345.678}),
                Command.create({'name': '/', 'price_unit': 345})
                ],

        })

        cls.bill.action_post()

        cls.invoice = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'date': fields.Date.from_string('2021-12-14'),
            'invoice_date': fields.Date.from_string('2021-12-14'),
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': 12345.678})],
        })


        cls.bill.open_expense_popup()
        expenses = cls.bill.billable_expenses_ids
        expenses_ids = expenses.ids
        expenses.write({'customer_id': cls.customer.id})
        cls.invoice.write({'partner_id': cls.customer.id})
        cls.invoice.from_expense_to_invoice(expenses_ids, 'item')
        cls.invoice.action_post()

    def test_set_invoice_to_draft_keep_billable_expenses(self):
        """
        Test set invoice to draft and keep all billable_expenses (2 lines)
        """
        expected_num_line = 3
        self.assertEqual(self.invoice.state, 'posted', 'Invoice must be in posted state')
        self._set_posted_invoice_to_draft(remove_expenses=False)
        self.assertEqual(len(self.invoice.invoice_line_ids),expected_num_line)
    
    def test_set_invoice_to_draft_remove_billable_expenses(self):
        """
        Test set invoice to draft and remove all billable_expenses
        """
        expected_num_line = 1
        self._set_posted_invoice_to_draft(remove_expenses=True)
        self.assertEqual(len(self.invoice.invoice_line_ids),expected_num_line)

    def test_expense_btn_name_keep_expense(self):
        """
        Test expense button name when set invoice to draft and keep all billable expenses
        """
        self._set_posted_invoice_to_draft(remove_expenses=False)
        self.assertEqual(self.invoice.expense_btn_name, '2 of 2 billable expense(s) added')
    
    def test_expense_btn_name_remove_expense(self):
        """
        Test expense button name when set invoice to draft and remove all billable expenses
        """
        self._set_posted_invoice_to_draft(remove_expenses=True)
        self.assertEqual(self.invoice.expense_btn_name, '2 billable expense(s) can be added')
    

    def _set_posted_invoice_to_draft(self, remove_expenses = False):
        cancel_form = Form(self.env['button.draft.message'], 'account_billable_expense_cancel.expense_invoice_to_draft_form_view')
        cancel_form.remove_expenses = remove_expenses
        cancel_form.move_id = self.invoice
        button_draft_message = cancel_form.save()
        button_draft_message.button_set_to_draft()
