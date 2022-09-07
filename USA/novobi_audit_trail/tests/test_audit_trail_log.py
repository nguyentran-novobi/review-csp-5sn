from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged
from odoo import Command

@tagged('post_install', '-at_install', 'basic_test')
class TestAuditTrailLog(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super(TestAuditTrailLog, cls).setUpClass()
        cls.payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': 100,
            'partner_id': cls.partner_a.id,
            'payment_method_line_id': cls.company_data['default_journal_bank'].inbound_payment_method_line_ids[0].id
        }

        cls.invoice_vals = {
                "move_type": "out_invoice",
                "partner_id": cls.partner_a.id,
                "date": "2021-12-12",
                "invoice_date": "2021-12-12",
                "invoice_date_due": "2021-12-30",
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
        }

    def test_create_logs(self):
        new_payment = self.env['account.payment'].create(self.payment_vals)
        payment_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_payment').id),
            ('res_id', '=', new_payment.id),
            ('author_id', '=', self.env.user.id),
            ('operation','=','create')
        ])
        expected_result = {
            'Amount': '100.0',
            'Currency': 'USD',
            'Customer/Vendor': self.partner_a.name,
            'Payment Method': 'Manual'
        }
        self.assertAuditLog(payment_logs, expected_result, 'create')

        # Create an journal entry
        new_move = self.env['account.move'].create(self.invoice_vals)
        journal_entry_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_move').id),
            ('res_id', '=', new_move.id),
            ('author_id', '=', self.env.user.id),
            ('operation','=','create')
        ])
        expected_result = {
            'Due Date': '2021-12-30',
            'Invoice/Bill Date': '2021-12-12',
            'Partner': self.partner_a.name,
        }
        self.assertAuditLog(journal_entry_logs, expected_result, 'create')

        journal_item_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_move_line').id),
            ('parent_id', '=', new_move.id),
            ('author_id', '=', self.env.user.id),
            ('operation','=','create')
        ])
        line_1_logs, line_2_logs = [], []
        current_resource = journal_item_logs[0].res_name
        for log in journal_item_logs:
            if log.res_name == current_resource:
                line_1_logs.append(log)
            else:
                line_2_logs.append(log)
        expected_result = {
            'Date': '2021-12-12',
            'Account': '400000 Product Sales',
            'Label': '/',
            'Quantity': '1.0',
            'Credit': '100.0',
            'Partner': self.partner_a.name
        }
        self.assertAuditLog(line_1_logs, expected_result, 'create')
        expected_result = {
            'Date': '2021-12-12',
            'Account': '121000 Account Receivable',
            'Quantity': '1.0',
            'Debit': '100.0',
            'Partner': self.partner_a.name
        }
        self.assertAuditLog(line_2_logs, expected_result, 'create')

    def test_edit_logs(self):
         # Create a payment
        new_payment = self.env['account.payment'].create(self.payment_vals)
        # Change payment partner
        new_payment.write({'partner_id': self.partner_b.id})
        expected_result = {
            'res_new_value': 'partner_b',
            'res_old_value': 'partner_a'
        }
        default_search_domain = [
            ('operation','=','write'),
            ('res_new_value', 'not in', [False, '']),
            ('res_old_value', 'not in', [False, '']),
            ('author_id', '=', self.env.user.id),
        ]
        payment_edit_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_payment').id),
            ('res_id', '=', new_payment.id), 
            ('res_field_name', '=', 'Partner')
        ])
        self.assertAuditLog(payment_edit_logs, expected_result, 'write')
        journal_entry_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_move').id),
            ('res_field_name', '=', 'Partner')
        ])
        self.assertAuditLog(journal_entry_logs, expected_result, 'write')
        journal_item_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_move_line').id),
            ('res_field_name', '=', 'Partner')
        ])
        self.assertAuditLog(journal_item_logs, expected_result, 'write')

        # Change payment amount
        new_payment.write({'amount': 200.0})
        expected_result = {
            'res_new_value': '200.0',
            'res_old_value': '100.0'
        }
        payment_edit_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_payment').id),
            ('res_id', '=', new_payment.id), 
            ('res_field_name', '=', 'Amount')
        ])
        self.assertAuditLog(payment_edit_logs, expected_result, 'write')
        journal_entry_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_move').id),
            ('res_field_name', '=', 'Total')
        ])
        self.assertAuditLog(journal_entry_logs, expected_result, 'write')
        journal_item_logs = self.env['audit.trail.log'].search([
            *default_search_domain,
            ('model_id', '=', self.env.ref('account.model_account_move_line').id),
            ('res_field_name', 'in', ['Debit', 'Credit'])
        ])
        self.assertAuditLog(journal_item_logs, expected_result, 'write')
    
    def test_delete_logs(self):
        new_payment = self.env['account.payment'].create(self.payment_vals)
        new_payment.unlink()
        payment_edit_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_payment').id),
            ('res_id', '=', new_payment.id),
            ('operation','=','unlink'),
        ])
        expected_result = {
            'model_id': self.env.ref('account.model_account_payment').id
        }
        self.assertAuditLog(payment_edit_logs, expected_result, 'unlink')
        expected_result = {
            'model_id': self.env.ref('account.model_account_move').id
        }
        journal_entry_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_move').id),
            ('operation','=','unlink'),
        ])
        self.assertAuditLog(journal_entry_logs, expected_result, 'unlink')
        expected_result = {
            'model_id': self.env.ref('account.model_account_move_line').id
        }
        journal_item_logs = self.env['audit.trail.log'].search([
            ('model_id', '=', self.env.ref('account.model_account_move_line').id),
            ('operation','=','unlink'),
        ])
        self.assertAuditLog(journal_item_logs, expected_result, 'unlink')

    def assertAuditLog(self, logs, expected_vals, operation):
        for log in logs:
            if operation == 'create':
                self.assertEqual(log.res_new_value, expected_vals[log.res_field_name])
            if operation == 'write':
                self.assertEqual(log.res_new_value, expected_vals['res_new_value'])
                self.assertEqual(log.res_old_value, expected_vals['res_old_value'])
            if operation == 'unlink':
                self.assertEqual(log.model_id.id, expected_vals['model_id'])
                self.assertEqual(log.operation, 'unlink')
