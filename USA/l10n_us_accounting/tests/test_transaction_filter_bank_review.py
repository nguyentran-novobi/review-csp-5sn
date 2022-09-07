from .common import TestInvoicingCommonUSAccounting
from odoo.tests.common import tagged
from odoo import Command

@tagged("post_install", "-at_install", "basic_test")
class TestTransactionFilters(TestInvoicingCommonUSAccounting):
    @classmethod
    def setUpClass(cls):
        super(TestTransactionFilters, cls).setUpClass()
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

        # Activate all filters
        cls.company = cls.env.company
        cls.company.bank_review_date_filter = True
        cls.company.bank_review_amount_filter = True
        cls.company.bank_review_transaction_type_filter = True


        cls.statement_data = {
            'name': 'BNK1',
            'date': '2022-02-02',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'line_ids': [Command.create({'payment_ref': '/', 'amount': 100.0, 'partner_id': cls.partner_a.id})],
        }

    def test_filters_domain(self):
        statement = self.env['account.bank.statement'].create(self.statement_data)
        statement_line = statement.line_ids
        reconciliation_widget = self.env['account.reconciliation.widget']

        domain = reconciliation_widget._get_domain_for_transaction_filters(statement_line)
        self.assertCountEqual(domain, [
            ('date', '<=', statement_line.date),
            ('credit', '=', 0),
            ('credit', '<=', 100.0), 
            ('debit', '<=', 100.0)
        ])
        
        self.company.bank_review_date_filter = False
        domain = reconciliation_widget._get_domain_for_transaction_filters(statement_line)
        self.assertCountEqual(domain, [
            ('credit', '=', 0),
            ('credit', '<=', 100.0), 
            ('debit', '<=', 100.0)
        ])

        statement_line.amount = -100.0
        domain = reconciliation_widget._get_domain_for_transaction_filters(statement_line)
        self.assertCountEqual(domain, [
            ('debit', '=', 0),
            ('credit', '<=', 100.0), 
            ('debit', '<=', 100.0)
        ])

    def test_get_matching_lines(self):
        statement = self.env['account.bank.statement'].create(self.statement_data)
        statement_line = statement.line_ids
        
        # Create some receivable lines
        invoice_1 = self.create_customer_invoice(amount=800, partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        receivable_1 = invoice_1.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')
        invoice_2 = self.create_customer_invoice(amount=100, partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        receivable_2 = invoice_2.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')
        invoice_3 = self.create_customer_invoice(amount=50, partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        receivable_3 = invoice_3.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')
        invoice_4 = self.create_customer_invoice(amount=50, partner_id=self.partner_a.id, date='2022-03-01', auto_validate=True)
        receivable_4 = invoice_4.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')

        invoice_EUR_1 = self.create_customer_invoice(amount=50, currency_id=self.curr_EUR.id ,partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        receivable_EUR_1 = invoice_EUR_1.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')
        invoice_EUR_2 = self.create_customer_invoice(amount=100, currency_id=self.curr_EUR.id ,partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        receivable_EUR_2 = invoice_EUR_2.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable')

        # Create payable line
        bill_1 = self.create_vendor_bill(amount=50 ,partner_id=self.partner_a.id, date='2022-01-01', auto_validate=True)
        payable_1 = bill_1.line_ids.filtered(lambda l: l.account_id.internal_type == 'payable')

        suggested_amls_ids = self._get_suggested_amls_ids(statement_line, self.partner_a)
        self.assertEqual(len(suggested_amls_ids), 3)
        self.assertCountEqual(suggested_amls_ids, [receivable_2.id, receivable_3.id, receivable_EUR_1.id])

        # Turn off amount filter
        self.company.bank_review_amount_filter = False

        suggested_amls_ids = self._get_suggested_amls_ids(statement_line, self.partner_a)
        self.assertEqual(len(suggested_amls_ids), 5)
        self.assertCountEqual(suggested_amls_ids, [receivable_1.id, receivable_2.id, receivable_3.id, receivable_EUR_1.id, receivable_EUR_2.id])

        # Turn off date filter
        self.company.bank_review_amount_filter = True
        self.company.bank_review_date_filter = False
        suggested_amls_ids = self._get_suggested_amls_ids(statement_line, self.partner_a)
        self.assertEqual(len(suggested_amls_ids), 4)
        self.assertCountEqual(suggested_amls_ids, [receivable_2.id, receivable_3.id, receivable_4.id, receivable_EUR_1.id])

        self.company.bank_review_date_filter = True
        self.company.bank_review_transaction_type_filter = False
        suggested_amls_ids = self._get_suggested_amls_ids(statement_line, self.partner_a)
        self.assertEqual(len(suggested_amls_ids), 4)
        self.assertCountEqual(suggested_amls_ids, [receivable_2.id, receivable_3.id, receivable_EUR_1.id, payable_1.id])


    def test_get_misc_lines(self):
        self.company_data['default_account_assets'].reconcile = True

        internal_transfer_1 = self.env['account.move'].create({
            'date': '2019-01-01',
            'journal_id': self.company_data['default_journal_cash'].id,
            'line_ids': [
                (0, 0, {
                    'name': 'line1',
                    'partner_id': self.partner_a.id,
                    'account_id': self.company_data['default_journal_bank'].default_account_id.id,
                    'debit': 1000.0,
                }),
                (0, 0, {
                    'name': 'line2',
                    'partner_id': self.partner_a.id,
                    'journal_id': self.company_data['default_journal_cash'].id,
                    'account_id': self.company_data['default_account_assets'].id,
                    'credit': 1000.0,
                }),
            ],
        })
        internal_transfer_1.action_post()

        # Different journal from statement
        internal_transfer_2 = self.env['account.move'].create({
            'date': '2019-01-01',
            'journal_id': self.company_data['default_journal_bank'].id,
            'line_ids': [
                (0, 0, {
                    'name': 'line1',
                    'account_id': self.company_data['default_journal_bank'].default_account_id.id,
                    'debit': 1000.0,
                }),
                (0, 0, {
                    'name': 'line1',
                    'account_id': self.company_data['default_account_assets'].id,
                    'credit': 1000.0,
                }),
            ],
        })
        internal_transfer_2.action_post()

        statement = self.env['account.bank.statement'].create({
            'name': 'test',
            'date': '2019-01-01',
            'balance_end_real': -1000.0,
            'journal_id': self.company_data['default_journal_cash'].id,
            'line_ids': [
                (0, 0, {
                    'payment_ref': 'line2',
                    'partner_id': self.partner_a.id,
                    'amount': -1000.0,
                    'date': '2019-01-01',
                }),
            ],
        })
        statement.button_post()
        statement_line = statement.line_ids

        suggested_amls_matching_ids = self._get_suggested_amls_ids(statement_line, self.partner_a)
        self.assertFalse(suggested_amls_matching_ids)
        suggested_amls_misc_ids = self._get_suggested_amls_ids(statement_line, self.partner_a, mode='misc')
        self.assertEqual(len(suggested_amls_misc_ids), 1)
        self.assertCountEqual(suggested_amls_misc_ids, [internal_transfer_1.line_ids[1].id])

    def _get_suggested_amls_ids(self, st_line, partner, mode='rp'):
        reconciliation_widget = self.env['account.reconciliation.widget']
        suggested_amls_recs = reconciliation_widget.get_move_lines_for_bank_statement_line(
            st_line.id,
            partner_id=partner.id,
            mode=mode,
        )
        suggested_amls_ids = [l['id'] for l in suggested_amls_recs]
        return suggested_amls_ids

