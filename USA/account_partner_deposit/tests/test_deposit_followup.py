from freezegun import freeze_time
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from .common import AccountTestInvoicingCommonDeposit


@tagged('post_install', '-at_install', 'basic_test')
class TestDepositAccountFollowupReports(TestAccountReportsCommon, AccountTestInvoicingCommonDeposit):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        report = cls.env['account.followup.report']
        cls.followup_options = {
            **report._get_options(None),
            'partner_id': cls.partner_a.id,
        }
        cls.followup_report = report.with_context(report._set_context(cls.followup_options))

        # Create deposits
        cls.cust_deposit_usd_1 = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=500.48,
                                                             date='2021-01-01', ref='ABC')
        cls.cust_deposit_usd_2 = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=200.36,
                                                             date='2021-01-02', ref='DEF')
        cls.cust_deposit_usd_3 = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=300.12,
                                                             date='2021-01-02', ref='JKL')
        cls.cust_deposit_eur_4 = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=200.36,
                                                             date='2021-01-02', currency_id=cls.curr_eur.id, ref='DEF')
        cls.cust_deposit_eur_5 = cls.create_customer_deposit(partner_id=cls.partner_a.id, amount=100.24,
                                                             date='2021-01-02', currency_id=cls.curr_eur.id, ref='JKL')

        # Create invoices
        cls.out_invoice_usd = cls.create_customer_invoice(amount=250.08, partner_id=cls.partner_a.id, date='2021-01-01',
                                                          auto_validate=True)
        cls.out_invoice_eur = cls.create_customer_invoice(amount=150, partner_id=cls.partner_a.id, date='2021-01-01',
                                                          currency_id=cls.curr_eur.id, auto_validate=True)

    def test_deposits_in_follow_up_report_company_currency(self):
        """
        Test posted deposits and draft deposits in follow-up report
        """
        self.cust_deposit_usd_1.action_post()
        self.cust_deposit_usd_2.action_post()

        # Filter out deposit lines
        deposit_lines = list(filter(lambda e: e.get('deposit_line', False),
                                    self.followup_report._get_lines(self.followup_options)))

        with freeze_time('2021-01-15'):
            # Draft deposits won't be shown
            self.assertLinesValues(
                deposit_lines,
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('BNK1/2021/01/0002',   '01/02/2021',   'DEF',          '',                 -200.36),
                    ('BNK1/2021/01/0001',   '01/01/2021',   'ABC',          '',                 -500.48),
                    ('',                    '',             '',             'Total Deposit',    -700.84)
                ]
            )

    def test_deposits_in_follow_up_report_partially_reconciled_company_currency(self):
        """
        Test partial reconciled deposit in follow-up report in company currency
        """
        self.cust_deposit_usd_1.action_post()
        self.cust_deposit_usd_2.action_post()

        # Reconcile invoice with deposit 1
        self._reconcile_invoice_and_payments(self.out_invoice_usd, self.cust_deposit_usd_1)

        # Filter out deposit lines
        deposit_lines = list(filter(lambda e: e.get('deposit_line', False),
                                    self.followup_report._get_lines(self.followup_options)))

        with freeze_time('2021-01-15'):
            self.assertLinesValues(
                deposit_lines,
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('BNK1/2021/01/0002',   '01/02/2021',   'DEF',          '',                 -200.36),
                    ('BNK1/2021/01/0001',   '01/01/2021',   'ABC',          '',                 -250.4),
                    ('',                    '',             '',             'Total Deposit',    -450.76)
                ]
            )

    def test_deposits_in_follow_up_report_fully_reconciled_company_currency(self):
        """
        Test fully reconciled deposit in follow-up report in company currency
        """
        self.cust_deposit_usd_1.action_post()
        self.cust_deposit_usd_2.action_post()

        # Reconcile invoice with deposit 2
        self._reconcile_invoice_and_payments(self.out_invoice_usd, self.cust_deposit_usd_2)

        # Filter out deposit lines
        deposit_lines = list(filter(lambda e: e.get('deposit_line', False),
                                    self.followup_report._get_lines(self.followup_options)))

        with freeze_time('2021-01-15'):
            self.assertLinesValues(
                deposit_lines,
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('BNK1/2021/01/0001',   '01/01/2021',   'ABC',          '',                 -500.48),
                    ('',                    '',             '',             'Total Deposit',    -500.48)
                ]
            )

    def test_deposits_in_follow_up_report_partially_reconciled_foreign_currency(self):
        """
        Test partially reconciled deposit in follow-up report in foreign currency
        """
        self.cust_deposit_usd_1.action_post()
        self.cust_deposit_eur_4.action_post()
        self.cust_deposit_eur_5.action_post()

        # Reconcile invoice with eur deposit 4
        self._reconcile_invoice_and_payments(self.out_invoice_eur, self.cust_deposit_eur_4)

        # Filter out deposit lines
        deposit_lines = list(filter(lambda e: e.get('deposit_line', False),
                                    self.followup_report._get_lines(self.followup_options)))

        with freeze_time('2021-01-15'):
            self.assertLinesValues(
                deposit_lines[:3],
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('BNK1/2021/01/0003',   '01/02/2021',   'JKL',          '',                 -100.24),
                    ('BNK1/2021/01/0002',   '01/02/2021',   'DEF',          '',                 -50.36),
                    ('',                    '',             '',             'Total Deposit',    -150.6)
                ],
                currency_map={4: {'currency': self.curr_eur}}
            )
            # There's an empty line between two currencies
            self.assertLinesValues(
                deposit_lines[3:],
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('',                    '',             '',             '',                 ''),
                    ('BNK1/2021/01/0001',   '01/01/2021',   'ABC',          '',                 -500.48),
                    ('',                    '',             '',             'Total Deposit',    -500.48)
                ]
            )

    def test_deposits_in_follow_up_report_fully_reconciled_foreign_currency(self):
        """
        Test fully reconciled deposit in follow-up report in foreign currency
        """
        self.cust_deposit_usd_1.action_post()
        self.cust_deposit_eur_4.action_post()
        self.cust_deposit_eur_5.action_post()

        # Reconcile invoice with eur deposit 5
        self._reconcile_invoice_and_payments(self.out_invoice_eur, self.cust_deposit_eur_5)

        # Filter out deposit lines
        deposit_lines = list(filter(lambda e: e.get('deposit_line', False),
                                    self.followup_report._get_lines(self.followup_options)))

        with freeze_time('2021-01-15'):
            self.assertLinesValues(
                deposit_lines[:2],
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('BNK1/2021/01/0002',   '01/02/2021',   'DEF',          '',                 -200.36),
                    ('',                    '',             '',             'Total Deposit',    -200.36)
                ],
                currency_map={4: {'currency': self.curr_eur}}
            )
            # There's an empty line between two currencies
            self.assertLinesValues(
                deposit_lines[2:],
                #   Deposit                 Date            Communication   Excluded            Total
                [   0,                      1,              2,              3,                  4],
                [
                    ('',                    '',             '',             '',                 ''),
                    ('BNK1/2021/01/0001',   '01/01/2021',   'ABC',          '',                 -500.48),
                    ('',                    '',             '',             'Total Deposit',    -500.48)
                ]
            )
