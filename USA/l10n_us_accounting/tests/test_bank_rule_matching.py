from datetime import date
from odoo import Command
from odoo.tests.common import Form, tagged
from odoo.exceptions import UserError
from .common import TestInvoicingCommonUSAccounting


@tagged('post_install', '-at_install', 'basic_test')
class TestBankRuleMatching(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company = cls.company_data['company']

        # Bank journals
        cls.bank_journal_usd = cls.company_data['default_journal_bank']
        cls.bank_journal_usd_copy = cls.bank_journal_usd.copy()

        # Bank rule
        cls.bank_rule = cls.env['account.reconcile.model'].create({
            'name': 'Transaction Matching Rule',
            'sequence': '1',
            'rule_type': 'invoice_matching',
            'auto_reconcile': False,
            'match_nature': 'both',
            'match_same_currency': True,
            'allow_payment_tolerance': False,
            'match_partner': True,
            'company_id': cls.company.id,
        })

        # Bank statement
        cls.bank_st = cls.env['account.bank.statement'].create({
            'name': 'test bank journal',
            'journal_id': cls.bank_journal_usd.id,
            'company_id': cls.company.id,
            'line_ids': [
                (0, 0, {
                    'date': '2022-02-01',
                    'payment_ref': 'payment 500',
                    'partner_id': cls.partner_a.id,
                    'amount': -2000,
                    'sequence': 1,
                }),
            ],
        })
        cls.bank_st.button_post()
        cls.bsl = cls.bank_st.line_ids

        # Check bank statement
        cls.check_bank_st = cls.env['account.bank.statement'].create({
            'name': 'test bank journal',
            'journal_id': cls.bank_journal_usd_copy.id,
            'company_id': cls.company.id,
            'line_ids': [
                (0, 0, {
                    'date': '2022-02-01',
                    'payment_ref': 'check #1',
                    'partner_id': cls.partner_b.id,
                    'amount': -500,
                    'sequence': 1,
                }),
                (0, 0, {
                    'date': '2022-02-01',
                    'payment_ref': '2 Check',
                    'partner_id': cls.partner_b.id,
                    'amount': -500,
                    'sequence': 2,
                }),
            ],
        })
        cls.check_bank_st.button_post()
        cls.check_bsl_1, cls.check_bsl_2 = cls.check_bank_st.line_ids

        # Payments
        cls.payment_out_1 = cls.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-01-31',
            auto_validate=True,
            journal_id=cls.bank_journal_usd.id
        )
        cls.payment_out_1_line = cls.payment_out_1.line_ids.filtered(
            lambda r: r.account_id.user_type_id.type not in ('receivable', 'payable'))

        cls.payment_out_2 = cls.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-01-31',
            auto_validate=False,
            journal_id=cls.bank_journal_usd_copy.id
        )

        cls.payment_out_3 = cls.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-02-05',
            auto_validate=False,
            journal_id=cls.bank_journal_usd.id
        )
        cls.payment_out_3_line = cls.payment_out_1.line_ids.filtered(
            lambda r: r.account_id.user_type_id.type not in ('receivable', 'payable'))

        cls.payment_in = cls.create_payment(
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-01-31',
            auto_validate=True,
            journal_id=cls.bank_journal_usd.id
        )

        # Bill
        cls.bill = cls.create_vendor_bill(
            date='2022-01-01',
            amount=400,
            partner_id=cls.partner_a.id,
            auto_validate=True
        )
        cls.bill_line = cls.bill.line_ids.filtered(
            lambda r: r.account_id.user_type_id.type in ('receivable', 'payable'))

        # Checks
        check_method = cls.env.ref('account_check_printing.account_payment_method_check')
        check_method_line = cls.bank_journal_usd_copy.outbound_payment_method_line_ids.filtered(
            lambda l: l.payment_method_id == check_method
        )

        cls.payment_out_check_1 = cls.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-01-31',
            auto_validate=True,
            journal_id=cls.bank_journal_usd_copy.id,
            payment_method_line_id=check_method_line.id,
            check_number='1'
        )
        cls.payment_out_check_1.check_number = '1'

        cls.payment_out_check_2 = cls.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=cls.partner_a.id,
            date='2022-01-31',
            auto_validate=True,
            journal_id=cls.bank_journal_usd_copy.id,
            payment_method_line_id=check_method_line.id,
            check_number='2'
        )
        cls.payment_out_check_2.check_number = '2'

        cls.payment_check_1_line = cls.payment_out_check_1.line_ids.filtered(
            lambda r: r.account_id.user_type_id.type not in ('receivable', 'payable'))
        cls.payment_check_2_line = cls.payment_out_check_2.line_ids.filtered(
            lambda r: r.account_id.user_type_id.type not in ('receivable', 'payable'))
        
     # ===== Helper =====

    def _check_statement_matching(self, rules, expected_values, statements=None):
        statement_lines = statements.mapped('line_ids').sorted()
        matching_values = rules._apply_rules(statement_lines, None)

        for st_line_id, values in matching_values.items():
            values.pop('reconciled_lines', None)
            values.pop('write_off_vals', None)
            self.assertDictEqual(values, expected_values[st_line_id])
    
    # ===== Test Normal Transactions Matching =====

    def test_transactions_have_difference_journal(self):
        self.payment_out_2.action_post()
        self._check_statement_matching(self.bank_rule, {
            self.bsl.id: {
                'aml_ids': [self.bill_line.id, self.payment_out_1_line.id], 'model': self.bank_rule, 'partner': self.partner_a}
        }, statements=self.bank_st)

    def test_transaction_date_after_statement_line_date(self):
        self.payment_out_3.action_post()
        self._check_statement_matching(self.bank_rule, {
            self.bsl.id: {
                'aml_ids': [self.bill_line.id, self.payment_out_1_line.id], 'model': self.bank_rule, 'partner': self.partner_a}
        }, statements=self.bank_st)

    # ===== Test Check Matching =====

    def test_matching_check(self):
        self._check_statement_matching(self.bank_rule, {
            self.check_bsl_1.id: {
                'aml_ids': [self.payment_check_1_line.id], 'model': self.bank_rule, 'partner': self.partner_b},
            self.check_bsl_2.id: {
                'aml_ids': [self.payment_check_2_line.id], 'model': self.bank_rule, 'partner': self.partner_b}
        }, statements=self.check_bank_st)

    def test_matching_check_with_different_amount(self):
        self.payment_out_check_2.action_draft()
        self.payment_out_check_2.amount = 550
        self.payment_out_check_2.check_number = '2'
        self.payment_out_check_2.action_post()
        self._check_statement_matching(self.bank_rule, {
            self.check_bsl_1.id: {
                'aml_ids': [self.payment_check_1_line.id], 'model': self.bank_rule, 'partner': self.partner_b},
            self.check_bsl_2.id: {
                'aml_ids': []}
        }, statements=self.check_bank_st)

    def test_matching_priority_with_check(self):
        self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=self.partner_b.id,
            date='2022-01-25',
            auto_validate=True,
            journal_id=self.bank_journal_usd_copy.id
        )
        self.create_payment(
            payment_type='outbound',
            partner_type='supplier',
            amount=500,
            partner_id=self.partner_b.id,
            date='2022-02-05',
            auto_validate=True,
            journal_id=self.bank_journal_usd_copy.id
        )

        self._check_statement_matching(self.bank_rule, {
            self.check_bsl_1.id: {
                'aml_ids': [self.payment_check_1_line.id], 'model': self.bank_rule, 'partner': self.partner_b},
            self.check_bsl_2.id: {
                'aml_ids': [self.payment_check_2_line.id], 'model': self.bank_rule, 'partner': self.partner_b}
        }, statements=self.check_bank_st)
