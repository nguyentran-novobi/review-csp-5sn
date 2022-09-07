from freezegun import freeze_time
from odoo.tests import tagged
from odoo import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from .common import TestInvoicingCommonUSAccounting


@tagged('post_install', '-at_install', 'basic_test')
class Test1099Report(TestAccountReportsCommon, TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.report_1099 = cls.env['vendor.1099.report']

        # 1099 account
        cls.expense_account_1099_1 = cls.copy_account(cls.company_data['default_account_expense'])
        cls.expense_account_1099_2 = cls.copy_account(cls.company_data['default_account_expense'])
        (cls.expense_account_1099_1 + cls.expense_account_1099_2).write({
            'account_eligible_1099': True
        })

        # Partners
        cls.partner_a.write({
            'street': 'Street 1',
            'street2': 'Street 2',
            'city': 'Austin',
            'state_id': cls.env.ref('base.state_us_44').id, # Texas
            'zip': '12345',
            'vendor_eligible_1099': True,
            'vat': '444555666'
        })

        # Outstanding accounts from setting
        cls.payment_debit_account = cls.company.account_journal_payment_debit_account_id
        cls.payment_credit_account = cls.company.account_journal_payment_credit_account_id
        cls.payment_credit_account_copy = cls.payment_credit_account.copy({'code': 1001})

        # Bank journals
        cls.bank_journal_usd = cls.company_data['default_journal_bank']
        cls.bank_journal_eur = cls.env['account.journal'].create({
            'name': 'Bank EUR',
            'type': 'bank',
            'code': 'BNK80',
            'currency_id': cls.curr_eur.id,
            'company_id': cls.company.id
        })

        # Payment methods
        cls.manual_in_method = cls.env.ref('account.account_payment_method_manual_in')
        cls.manual_out_method = cls.env.ref('account.account_payment_method_manual_out')

        # Outgoing payment method lines in Journal
        cls.method_1 = cls.env['account.payment.method.line'].create({
                'name': 'Manual 1',
                'payment_method_id': cls.manual_out_method.id,
                'payment_account_id': cls.payment_credit_account_copy.id,
                'journal_id': cls.bank_journal_usd.id
            })

        cls.method_2 = cls.env['account.payment.method.line'].create({
                'name': 'Manual 2',
                'payment_method_id': cls.manual_out_method.id,
                'journal_id': cls.bank_journal_usd.id
            })

        cls.method_credit_card = cls.env['account.payment.method.line'].create({
                'name': 'Credit Card',
                'payment_method_id': cls.manual_out_method.id,
                'journal_id': cls.bank_journal_usd.id,
                'is_credit_card': True
            })

        # Incoming payment method lines in Journal
        cls.method_incoming_1 = cls.env['account.payment.method.line'].create({
            'name': 'Manual 1',
            'payment_method_id': cls.manual_in_method.id,
            'payment_account_id': cls.payment_credit_account_copy.id,
            'journal_id': cls.bank_journal_usd.id
        })

        cls.method_incoming_2 = cls.env['account.payment.method.line'].create({
            'name': 'Manual 2',
            'payment_method_id': cls.manual_in_method.id,
            'journal_id': cls.bank_journal_usd.id
        })

        cls.method_credit_card_incoming = cls.env['account.payment.method.line'].create({
            'name': 'Credit Card',
            'payment_method_id': cls.manual_in_method.id,
            'journal_id': cls.bank_journal_usd.id,
            'is_credit_card': True
        })

        # Set currency rates
        cls.env.ref('base.EUR').write({
            'rate_ids': [
                Command.clear(),
                Command.create({
                    'name': '2022-01-01',
                    'rate': 0.8,
                }), Command.create({
                    'name': '2022-01-10',
                    'rate': 0.85,
                })
            ]})

    @freeze_time('2022-01-01')
    def test_1099_vendor_bill(self):
        # Create bill
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': '/',
                    'price_unit': 100,
                    'account_id': self.company_data['default_account_expense'].id
                }),
                Command.create({
                    'name': '/',
                    'price_unit': 200,
                    'account_id': self.expense_account_1099_1.id
                }),
                Command.create({
                    'name': '/',
                    'price_unit': 300,
                    'account_id': self.expense_account_1099_2.id
                })
            ]
        })
        bill.action_post()

        # Create payments
        payment_1 = self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=50,
            auto_validate=True,
            payment_method_line_id=self.method_1.id
        )

        payment_2 = self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=250,
            auto_validate=True,
            payment_method_line_id=self.method_2.id
        )

        payment_credit_card = self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=300,
            auto_validate=True,
            payment_method_line_id=self.method_credit_card.id
        )

        payment_moves = (payment_1 + payment_2 + payment_credit_card).mapped('move_id')

        self._reconcile_invoice_and_payments(bill, payment_moves)

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2022', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2022-01-01', 'date_to': '2022-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                   EIN/SSN Number  Address                              Amount Paid
            [    0,             1,              2,                                   3],
            [
                ('partner_a',   '444555666',   'Street 1 Street 2 Austin TX 12345', '$ 250.00'),
                ('Total',       '',            '',                                  '$ 250.00')
            ]
        )

    @freeze_time('2022-01-01')
    def test_1099_vendor_bill_foreign_currency(self):
        # Create bill
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-01-01',
            'currency_id': self.curr_eur.id,
            'invoice_line_ids': [
                Command.create({
                    'name': '/',
                    'price_unit': 300,
                    'account_id': self.expense_account_1099_1.id
                })
            ]
        })
        bill.action_post()

        # Partner is not 1099 vendor
        bill2 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_b.id,
            'invoice_date': '2022-01-01',
            'currency_id': self.curr_eur.id,
            'invoice_line_ids': [
                Command.create({
                    'name': '/',
                    'price_unit': 200,
                    'account_id': self.expense_account_1099_1.id
                })
            ]
        })
        bill2.action_post()

        # Create payment
        vendor_payment = self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            partner_id=self.partner_a.id,
            amount=500,
            date='2022-01-01',
            currency_id=self.curr_eur.id,
            journal_id=self.bank_journal_eur.id,
            auto_validate=True
        )

        self._reconcile_invoice_and_payments(bill, vendor_payment)
        self._reconcile_invoice_and_payments(bill2, vendor_payment)

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2022', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2022-01-01', 'date_to': '2022-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                   EIN/SSN Number  Address                              Amount Paid
            [    0,             1,              2,                                   3],
            [
                ('partner_a',   '444555666',   'Street 1 Street 2 Austin TX 12345', '$ 375.00'),
                ('Total',       '',            '',                                  '$ 375.00')
            ]
        )

    @freeze_time('2022-01-01')
    def test_1099_manual_entry(self):
        partner_a_copy = self.partner_a.copy()

        entry_1 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2022-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 0.0, 'credit': 500,
                        'account_id': self.bank_journal_usd.default_account_id.id}),
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 500, 'credit': 0,
                        'account_id': self.expense_account_1099_1.id})
            ],
        })

        entry_2 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2022-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 100, 'credit': 0,
                        'account_id': self.bank_journal_usd.default_account_id.id}),
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 0, 'credit': 100,
                        'account_id': self.expense_account_1099_1.id})
            ],
        })

        entry_3 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2022-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'partner_id': partner_a_copy.id, 'debit': 0, 'credit': 500,
                        'account_id': self.bank_journal_usd.default_account_id.id}),
                (0, 0, {'partner_id': partner_a_copy.id, 'debit': 100, 'credit': 0,
                        'account_id': self.expense_account_1099_1.id}),
                (0, 0, {'partner_id': partner_a_copy.id, 'debit': 200, 'credit': 0,
                        'account_id': self.expense_account_1099_2.id}),
                (0, 0, {'partner_id': partner_a_copy.id, 'debit': 200, 'credit': 0,
                        'account_id': self.company_data['default_account_assets'].id})
            ],
        })

        (entry_1 + entry_2 + entry_3).action_post()

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2022', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2022-01-01', 'date_to': '2022-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                           EIN/SSN Number  Address                               Amount Paid
            [    0,                     1,              2,                                    3],
            [
                ('partner_a',           '444555666',   'Street 1 Street 2 Austin TX 12345',  '$ 400.00'),
                ('partner_a (copy)',    '444555666',   'Street 1 Street 2 Austin TX 12345',  '$ 300.00'),
                ('Total',               '',            '',                                   '$ 700.00')
            ]
        )

    @freeze_time('2022-01-01')
    def test_1099_customer_invoice(self):
        # Create invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': '/',
                    'price_unit': 100,
                    'account_id': self.company_data['default_account_expense'].id
                }),
                Command.create({
                    'name': '/',
                    'price_unit': 200,
                    'account_id': self.expense_account_1099_1.id
                }),
                Command.create({
                    'name': '/',
                    'price_unit': 300,
                    'account_id': self.expense_account_1099_2.id
                })
            ]
        })
        invoice.action_post()

        # Create payments
        payment_1 = self.create_payment(
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=50,
            auto_validate=True,
            payment_method_line_id=self.method_incoming_1.id
        )

        payment_2 = self.create_payment(
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=250,
            auto_validate=True,
            payment_method_line_id=self.method_incoming_2.id
        )

        payment_credit_card = self.create_payment(
            partner_id=self.partner_a.id,
            date='2022-01-01',
            amount=300,
            auto_validate=True,
            payment_method_line_id=self.method_credit_card_incoming.id
        )

        payment_moves = (payment_1 + payment_2 + payment_credit_card).mapped('move_id')

        self._reconcile_invoice_and_payments(invoice, payment_moves)

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2022', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2022-01-01', 'date_to': '2022-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                   EIN/SSN Number  Address                              Amount Paid
            [    0,             1,              2,                                   3],
            [
                ('partner_a',  '444555666',    'Street 1 Street 2 Austin TX 12345', '$ -250.00'),
                ('Total',      '',             '',                                  '$ -250.00')
            ]
        )

    @freeze_time('2022-01-01')
    def test_1099_customer_invoice_foreign_currency(self):
        # Create invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2022-01-01',
            'currency_id': self.curr_eur.id,
            'invoice_line_ids': [
                Command.create({
                    'name': '/',
                    'price_unit': 300,
                    'account_id': self.expense_account_1099_1.id
                })
            ]
        })
        invoice.action_post()

        # Create payment
        payment = self.create_payment(
            partner_id=self.partner_a.id,
            amount=500,
            date='2022-01-01',
            currency_id=self.curr_eur.id,
            journal_id=self.bank_journal_eur.id,
            auto_validate=True
        )

        self._reconcile_invoice_and_payments(invoice, payment)

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2022', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2022-01-01', 'date_to': '2022-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                   EIN/SSN Number  Address                              Amount Paid
            [    0,             1,              2,                                   3],
            [
                ('partner_a',  '444555666',    'Street 1 Street 2 Austin TX 12345', '$ -375.00'),
                ('Total',      '',             '',                                  '$ -375.00')
            ]
        )

    @freeze_time('2022-01-01')
    def test_1099_period_filter(self):
        entry_1 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2022-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 0.0, 'credit': 500,
                        'account_id': self.bank_journal_usd.default_account_id.id}),
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 500, 'credit': 0,
                        'account_id': self.expense_account_1099_1.id})
            ],
        })
        entry_1.action_post()

        entry_2 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2021-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 0.0, 'credit': 100,
                        'account_id': self.bank_journal_usd.default_account_id.id}),
                (0, 0, {'partner_id': self.partner_a.id, 'debit': 100, 'credit': 0,
                        'account_id': self.expense_account_1099_1.id})
            ],
        })
        entry_2.action_post()

        # Check 1099 report
        report_options = {'allow_domestic': False, 'fiscal_position': 'all',
                          'date': {'string': '2021', 'period_type': 'fiscalyear', 'mode': 'range',
                                   'strict_range': False, 'date_from': '2021-01-01', 'date_to': '2021-12-31',
                                   'filter': 'this_year'}}

        report_lines = self.report_1099._get_lines(report_options)

        self.assertLinesValues(
            report_lines,
            #                           EIN/SSN Number  Address                               Amount Paid
            [    0,                     1,              2,                                    3],
            [
                ('partner_a',          '444555666',    'Street 1 Street 2 Austin TX 12345',  '$ 100.00'),
                ('Total',              '',             '',                                   '$ 100.00')
            ]
        )
