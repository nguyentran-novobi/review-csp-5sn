from odoo import Command
from odoo.tests.common import Form, tagged
from datetime import date
from .common import TestInvoicingCommonBatchAdjustment


@tagged('post_install', '-at_install', 'basic_test')
class TestAdjustmentLinesInBatchPayment(TestInvoicingCommonBatchAdjustment):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Set currency rates
        cls.env.ref('base.EUR').write({
            'rate_ids': [Command.clear(), Command.create({
                'name': '2022-01-01',
                'rate': 0.8,
            }), Command.create({
                'name': '2022-01-10',
                'rate': 0.85,
            })]
        })

        # Customer payments USD
        cls.payment_500_usd = cls.create_payment(
            partner_id=cls.partner_a.id, amount=500, date='2022-01-01', auto_validate=True)
        cls.payment_300_usd = cls.create_payment(
            partner_id=cls.partner_b.id, amount=300, date='2022-01-01', auto_validate=True)

        # Customer payments EUR
        cls.payment_500_eur = cls.create_payment(
            partner_id=cls.partner_a.id, amount=500, date='2022-01-01', currency_id=cls.curr_eur.id,
            journal_id=cls.bank_journal_eur.id, auto_validate=True)
        cls.payment_300_eur = cls.create_payment(
            partner_id=cls.partner_b.id, amount=300, date='2022-01-01', currency_id=cls.curr_eur.id,
            journal_id=cls.bank_journal_eur.id, auto_validate=True)

        # Vendor payments USD
        cls.vendor_payment_500_usd = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_a.id, amount=500,
            date='2022-01-01', auto_validate=True)
        cls.vendor_payment_300_usd = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_b.id, amount=300,
            date='2022-01-01', auto_validate=True)

        # Vendor payments EUR
        cls.vendor_payment_500_eur = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_a.id, amount=500, date='2022-01-01',
            currency_id=cls.curr_eur.id, journal_id=cls.bank_journal_eur.id, auto_validate=True)
        cls.vendor_payment_300_eur = cls.create_payment(
            payment_type='outbound', partner_type='supplier', partner_id=cls.partner_b.id, amount=300, date='2022-01-01',
            currency_id=cls.curr_eur.id, journal_id=cls.bank_journal_eur.id, auto_validate=True)

        # Adjustment lines data
        fund_line_commands = [
            Command.create({
                'line_payment_date': '2022-01-1',
                'line_partner_id': cls.partner_a.id,
                'line_account_id': cls.account_asset_1.id,
                'line_communication': 'Line 1',
                'line_amount': 15.25
            }),
            Command.create({
                'line_payment_date': '2022-01-15',
                'line_partner_id': cls.partner_b.id,
                'line_account_id': cls.account_asset_2.id,
                'line_communication': 'Line 2',
                'line_amount': -20.48
            })
        ]

        # Batch payment inbound
        cls.batch_inbound_usd = cls.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_usd.id,
            'payment_ids': [Command.link(cls.payment_500_usd.id), Command.link(cls.payment_300_usd.id)],
            'payment_method_id': cls.manual_in_method.id,
            'fund_line_ids': fund_line_commands
        })
        cls.batch_inbound_eur = cls.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_eur.id,
            'payment_ids': [Command.link(cls.payment_500_eur.id), Command.link(cls.payment_300_eur.id)],
            'payment_method_id': cls.manual_in_method.id,
            'fund_line_ids': fund_line_commands
        })

        # Batch payment outbound
        cls.batch_outbound_usd = cls.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_usd.id,
            'payment_ids': [Command.link(cls.vendor_payment_500_usd.id), Command.link(cls.vendor_payment_300_usd.id)],
            'payment_method_id': cls.manual_out_method.id,
            'fund_line_ids': fund_line_commands
        })
        cls.batch_outbound_eur = cls.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'date': '2022-01-10',
            'journal_id': cls.bank_journal_eur.id,
            'payment_ids': [Command.link(cls.vendor_payment_500_eur.id), Command.link(cls.vendor_payment_300_eur.id)],
            'payment_method_id': cls.manual_out_method.id,
            'fund_line_ids': fund_line_commands
        })

    # -------------------------------------------------------------------------
    # INBOUND BATCH PAYMENT
    # -------------------------------------------------------------------------

    def test_adjustment_line_and_its_journal_entry_sync_when_create(self):
        """
        Create new adjustment lines and check its journal entry
        """
        fund_lines = self.batch_inbound_usd.fund_line_ids.sorted('line_amount')

        # Check batch payment amount
        self.assertEqual(self.batch_inbound_usd.amount, 794.77)

        # Check journal items
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.payment_debit_account.id,
                'debit': 0,
                'credit': 20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.company_data['currency'].id
            },
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.account_asset_2.id,
                'debit': 20.48,
                'credit': 0,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.company_data['currency'].id
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.account_asset_1.id,
                'debit': 0,
                'credit': 15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.company_data['currency'].id
            },
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.payment_debit_account.id,
                'debit': 15.25,
                'credit': 0,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.company_data['currency'].id
            }
        ])

    def test_adjustment_line_and_its_journal_entry_sync_when_write(self):
        """
        Update adjustment lines and check its journal entry
        """
        # Update adjustment lines
        fund_lines = self.batch_inbound_usd.fund_line_ids.sorted('line_amount')
        fund_lines[0].write({
            'line_account_id': self.account_asset_1.id,
            'line_amount': -30.48
        })
        fund_lines[1].write({
            'line_payment_date': '2022-01-30',
            'line_partner_id': self.partner_b.id,
            'line_communication': 'Line 1 updated',
        })

        # Check journal items
        fund_lines = self.batch_inbound_usd.fund_line_ids.sorted('line_amount')
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'account_id': self.payment_debit_account.id,
                'debit': 0,
                'credit': 30.48,
            },
            {
                'account_id': self.account_asset_1.id,
                'debit': 30.48,
                'credit': 0,
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 30),
                'debit': 0,
                'credit': 15.25,
                'partner_id': self.partner_b.id,
                'name': 'Line 1 updated'
            },
            {
                'date': date(2022, 1, 30),
                'debit': 15.25,
                'credit': 0,
                'partner_id': self.partner_b.id,
                'name': 'Line 1 updated'
            }
        ])

    def test_adjustment_line_and_its_journal_entry_sync_when_create_foreign_currency(self):
        """
        Create new adjustment lines in foreign currency and check its journal entry
        """
        fund_lines = self.batch_inbound_eur.fund_line_ids.sorted('line_amount')

        # Check batch payment amount
        self.assertEqual(self.batch_inbound_eur.amount, 794.77)

        # Check journal items
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.payment_debit_account.id,
                'debit': 0,
                'credit': 24.09,
                'amount_currency': -20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.curr_eur.id
            },
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.account_asset_2.id,
                'debit': 24.09,
                'credit': 0,
                'amount_currency': 20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.curr_eur.id
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.account_asset_1.id,
                'debit': 0,
                'credit': 19.06,
                'amount_currency': -15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.curr_eur.id
            },
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.payment_debit_account.id,
                'debit': 19.06,
                'credit': 0,
                'amount_currency': 15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.curr_eur.id
            }
        ])

    def test_adjustment_line_and_its_journal_entry_sync_when_write_foreign_currency(self):
        """
        Update adjustment lines in foreign currency and check its journal entry
        """
        # Update adjustment lines
        fund_lines = self.batch_inbound_eur.fund_line_ids.sorted('line_amount')
        fund_lines[0].write({
            'line_account_id': self.account_asset_1.id,
            'line_amount': -30.48
        })
        fund_lines[1].write({
            'line_payment_date': '2022-01-30',
            'line_partner_id': self.partner_b.id,
            'line_communication': 'Line 1 updated',
        })

        # Check journal items
        fund_lines = self.batch_inbound_eur.fund_line_ids.sorted('line_amount')
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'account_id': self.payment_debit_account.id,
                'debit': 0,
                'credit': 35.86,
                'amount_currency': -30.48
            },
            {
                'account_id': self.account_asset_1.id,
                'debit': 35.86,
                'credit': 0,
                'amount_currency': 30.48
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 30),
                'debit': 0,
                'credit': 17.94,
                'partner_id': self.partner_b.id,
                'name': 'Line 1 updated'
            },
            {
                'date': date(2022, 1, 30),
                'debit': 17.94,
                'credit': 0,
                'partner_id': self.partner_b.id,
                'name': 'Line 1 updated'
            }
        ])

    # -------------------------------------------------------------------------
    # OUTBOUND BATCH PAYMENT
    # -------------------------------------------------------------------------

    def test_adjustment_line_and_its_journal_entry_sync_when_create_outbound(self):
        """
        Create new adjustment lines and check its journal entry
        """
        fund_lines = self.batch_outbound_usd.fund_line_ids.sorted('line_amount')

        # Check batch payment amount
        self.assertEqual(self.batch_outbound_usd.amount, -794.77)

        # Check journal items
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.account_asset_2.id,
                'debit': 0,
                'credit': 20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.company_data['currency'].id
            },
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.payment_credit_account.id,
                'debit': 20.48,
                'credit': 0,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.company_data['currency'].id
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.payment_credit_account.id,
                'debit': 0,
                'credit': 15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.company_data['currency'].id
            },
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_usd.id,
                'account_id': self.account_asset_1.id,
                'debit': 15.25,
                'credit': 0,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.company_data['currency'].id
            }
        ])

    def test_adjustment_line_and_its_journal_entry_sync_when_create_foreign_currency_outbound(self):
        """
        Create new adjustment lines in foreign currency and check its journal entry
        """
        fund_lines = self.batch_outbound_eur.fund_line_ids.sorted('line_amount')

        # Check batch payment amount
        self.assertEqual(self.batch_outbound_eur.amount, -794.77)

        # Check journal items
        self.assertRecordValues(fund_lines[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.account_asset_2.id,
                'debit': 0,
                'credit': 24.09,
                'amount_currency': -20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.curr_eur.id
            },
            {
                'date': date(2022, 1, 15),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.payment_credit_account.id,
                'debit': 24.09,
                'credit': 0,
                'amount_currency': 20.48,
                'partner_id': self.partner_b.id,
                'name': 'Line 2',
                'currency_id': self.curr_eur.id
            }
        ])
        self.assertRecordValues(fund_lines[1].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.payment_credit_account.id,
                'debit': 0,
                'credit': 19.06,
                'amount_currency': -15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.curr_eur.id
            },
            {
                'date': date(2022, 1, 1),
                'journal_id': self.bank_journal_eur.id,
                'account_id': self.account_asset_1.id,
                'debit': 19.06,
                'credit': 0,
                'amount_currency': 15.25,
                'partner_id': self.partner_a.id,
                'name': 'Line 1',
                'currency_id': self.curr_eur.id
            }
        ])

    # -------------------------------------------------------------------------
    # OUTSTANDING ACCOUNT OF ADJUSTMENT LINES
    # -------------------------------------------------------------------------

    def test_outstanding_account_of_adjustment_line_inbound(self):
        payment_debit_account_1 = self.payment_debit_account.copy({'code': 1001})
        payment_debit_account_2 = self.payment_debit_account.copy({'code': 1002})

        self.env['account.payment.method.line'].create([
            {
                'name': 'Manual 1',
                'payment_method_id': self.manual_in_method.id,
                'payment_account_id': payment_debit_account_1.id,
                'sequence': 1,
                'journal_id': self.bank_journal_usd.id
            },
            {
                'name': 'Manual 2',
                'payment_method_id': self.manual_in_method.id,
                'payment_account_id': payment_debit_account_2.id,
                'sequence': 2,
                'journal_id': self.bank_journal_usd.id
            }
        ])

        inbound_batch = self.env['account.batch.payment'].create({
            'batch_type': 'inbound',
            'date': '2022-01-10',
            'journal_id': self.bank_journal_usd.id,
            'payment_ids': [Command.link(self.payment_500_usd.id)],
            'payment_method_id': self.manual_in_method.id,
            'fund_line_ids': [
                Command.create({
                    'line_payment_date': '2022-01-1',
                    'line_partner_id': self.partner_a.id,
                    'line_account_id': self.account_asset_1.id,
                    'line_communication': 'Line 1',
                    'line_amount': 10
                })
            ]
        })

        self.assertRecordValues(inbound_batch.fund_line_ids[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'account_id': self.account_asset_1.id,
                'debit': 0,
                'credit': 10,
            },
            {
                'account_id': payment_debit_account_1.id,
                'debit': 10,
                'credit': 0,
            }
        ])

    def test_outstanding_account_of_adjustment_line_outbound(self):
        payment_credit_account_1 = self.payment_credit_account.copy({'code': 1001})
        payment_credit_account_2 = self.payment_credit_account.copy({'code': 1002})

        self.env['account.payment.method.line'].create([
            {
                'name': 'Manual 1',
                'payment_method_id': self.manual_out_method.id,
                'payment_account_id': payment_credit_account_1.id,
                'sequence': 2,
                'journal_id': self.bank_journal_usd.id
            },
            {
                'name': 'Manual 2',
                'payment_method_id': self.manual_out_method.id,
                'payment_account_id': payment_credit_account_2.id,
                'sequence': 1,
                'journal_id': self.bank_journal_usd.id
            }
        ])

        outbound_batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'date': '2022-01-10',
            'journal_id': self.bank_journal_usd.id,
            'payment_ids': [Command.link(self.vendor_payment_500_usd.id)],
            'payment_method_id': self.manual_out_method.id,
            'fund_line_ids': [
                Command.create({
                    'line_payment_date': '2022-01-1',
                    'line_partner_id': self.partner_a.id,
                    'line_account_id': self.account_asset_1.id,
                    'line_communication': 'Line 1',
                    'line_amount': -10
                })
            ]
        })

        self.assertRecordValues(outbound_batch.fund_line_ids[0].mapped('account_move_id.line_ids').sorted('balance'), [
            {
                'account_id': self.account_asset_1.id,
                'debit': 0,
                'credit': 10,
            },
            {
                'account_id': payment_credit_account_2.id,
                'debit': 10,
                'credit': 0,
            }
        ])

    # -------------------------------------------------------------------------
    # STATE OF BATCH PAYMENT
    # -------------------------------------------------------------------------

    def test_batch_payment_state_when_set_adjustment_line_to_draft(self):
        self.batch_inbound_usd.validate_batch_button()
        fund_lines = self.batch_inbound_usd.fund_line_ids

        # Check batch payment and adjustment lines state
        self.assertEqual(self.batch_inbound_usd.state, 'sent')
        self.assertTrue(all(move.state == 'posted' for move in fund_lines.mapped('account_move_id')))

        # Set to draft adjustment line
        self.batch_inbound_usd.fund_line_ids[0].account_move_id.button_draft()
        self.assertEqual(self.batch_inbound_usd.state, 'draft')

        self.batch_inbound_usd.fund_line_ids[0].account_move_id.action_post()
        self.assertEqual(self.batch_inbound_usd.state, 'sent')

        # Unsent payment
        self.batch_inbound_usd.payment_ids[0].unmark_as_sent()
        self.assertEqual(self.batch_inbound_usd.state, 'draft')

        self.batch_inbound_usd.payment_ids[0].mark_as_sent()
        self.assertEqual(self.batch_inbound_usd.state, 'sent')
