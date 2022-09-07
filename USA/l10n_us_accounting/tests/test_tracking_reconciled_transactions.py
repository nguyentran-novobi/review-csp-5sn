from odoo import fields, Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import Warning
from .common import TestInvoicingCommonUSAccounting


@tagged("post_install", "-at_install", "basic_test")
class TestTrackingReconciledTransactions(TestInvoicingCommonUSAccounting):
    @classmethod
    def setUpClass(cls):
        super(TestTrackingReconciledTransactions, cls).setUpClass()
        cls.new_bank_journal = cls.env["account.journal"].create(
            {"name": "New Bank", "type": "bank", "code": "NB"}
        )
        cls.statement_data = {
            "name": "BNK1",
            "date": "2022-02-02",
            "journal_id": cls.new_bank_journal.id,
            "line_ids": [
                Command.create(
                    {
                        "payment_ref": "Deposit",
                        "amount": 600.0,
                        "partner_id": cls.partner_a.id,
                    }
                ),
                Command.create(
                    {
                        "payment_ref": "Payment",
                        "amount": -600.0,
                        "partner_id": cls.partner_a.id,
                    }
                ),
            ],
        }
        cls.reconcile_screen = cls.env["usa.bank.reconciliation"]

        # New discrepancy account
        cls.discrepancy_account = cls.copy_account(
            cls.company_data["default_journal_bank"].default_account_id
        )

        cls.in_payment_200 = cls.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": 200,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        cls.in_payment_300 = cls.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": 300,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        cls.in_payment_100 = cls.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": 100,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        cls.out_payment_200 = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "amount": 200,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        cls.out_payment_300 = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "amount": 300,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        cls.out_payment_100 = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "amount": 100,
                "journal_id": cls.new_bank_journal.id,
                "partner_id": cls.partner_a.id,
                "date": "2022-02-22",
            }
        )

        (
            cls.in_payment_100
            + cls.in_payment_200
            + cls.in_payment_300
            + cls.out_payment_100
            + cls.out_payment_200
            + cls.out_payment_300
        ).action_post()

        deposit_line_ids = (cls.in_payment_100 + cls.in_payment_200 + cls.in_payment_300).line_ids
        payment_line_ids = (cls.out_payment_100 + cls.out_payment_200 + cls.out_payment_300).line_ids
        statement = cls.env['account.bank.statement'].create(cls.statement_data)
        to_reconcile_debit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount > 0).ids
        to_reconcile_credit_bsl_ids = statement.line_ids.filtered(lambda line: line.amount < 0).ids
        debit_lines_vals_list = [{'id': line.id} for line in deposit_line_ids.filtered(lambda line: line.debit)]
        credit_lines_vals_list = [{'id': line.id} for line in payment_line_ids.filtered(lambda line: line.credit)]
        statement.button_post()
        cls.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_debit_bsl_ids, [{'lines_vals_list': debit_lines_vals_list}])
        cls.env['account.reconciliation.widget'].process_bank_statement_line(to_reconcile_credit_bsl_ids, [{'lines_vals_list': credit_lines_vals_list}])
        cls.session = cls.create_new_session(cls.new_bank_journal, 0, 0)

    def test_tracking_cancel_transactions(self):
        aml_ids = self.session._get_transactions()
        self.assertEqual(len(aml_ids), 6)
        self.session.aml_ids = aml_ids
        # Reconcile all transactions
        self.session.check_difference_amount(
            aml_ids = [],
            difference = 0,
            cleared_payments = 600,
            cleared_deposits = 600
        )
        self.assertFalse(self.session.change_transaction_ids)
        self.assertEqual(self.session.change_amount, 0)

        # Set to draft transactions
        (self.in_payment_100 + self.in_payment_200).action_draft()
        changed_ids = self.session.change_transaction_ids
        self.assertEqual(len(changed_ids), 2)
        self.assertRecordValues(changed_ids, expected_values=[
            {'change_status': 'canceled'},
            {'change_status': 'canceled'}
        ])
        self.session._compute_change_amount()
        self.assertEqual(self.session.change_amount, -300)

        # Cancel transactions
        (self.out_payment_200 + self.in_payment_300).action_draft()
        changed_ids = self.session.change_transaction_ids
        self.assertEqual(len(changed_ids), 4)
        self.assertRecordValues(changed_ids, expected_values=[
            {'change_status': 'canceled'},
            {'change_status': 'canceled'},
            {'change_status': 'canceled'},
            {'change_status': 'canceled'}
        ])
        self.session._compute_change_amount()
        self.assertEqual(self.session.change_amount, -400)

    def test_tracking_delete_transactions(self):
        aml_ids = self.session._get_transactions()
        self.assertEqual(len(aml_ids), 6)
        self.session.aml_ids = aml_ids
        # Reconcile all transactions
        self.session.check_difference_amount(
            aml_ids = [],
            difference = 0,
            cleared_payments = 600,
            cleared_deposits = 600
        )
        self.assertFalse(self.session.change_transaction_ids)
        self.assertEqual(self.session.change_amount, 0)

        # Set to draft transactions
        (self.in_payment_100 + self.in_payment_200).action_draft()
        changed_ids = self.session.change_transaction_ids
        self.assertEqual(len(changed_ids), 2)
        self.assertRecordValues(changed_ids, expected_values=[
            {'change_status': 'canceled'},
            {'change_status': 'canceled'}
        ])
        # Delete transactions
        (self.in_payment_100 + self.in_payment_200).unlink()
        changed_ids = self.session.change_transaction_ids
        self.assertEqual(len(changed_ids), 2)
        self.assertRecordValues(changed_ids, expected_values=[
            {'change_status': 'deleted'},
            {'change_status': 'deleted'}
        ])
        self.assertEqual(self.session.change_amount, -300)
        
    
