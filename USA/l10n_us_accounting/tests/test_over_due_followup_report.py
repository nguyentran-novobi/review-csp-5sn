from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged
from odoo import fields, Command
from freezegun import freeze_time


@tagged("post_install", "-at_install", "basic_test")
class TestOverdueFollowUpReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super(TestOverdueFollowUpReport, cls).setUpClass()

        cls.report = cls.env['account.followup.report']

        cls.curr_USD = cls.env.ref("base.USD")
        cls.curr_EUR = cls.env.ref("base.EUR")

        # ==== Due Invoices ====

        invoice_data = {
                "move_type": "out_invoice",
                "partner_id": cls.partner_a.id,
                "date": fields.Date.from_string("2021-12-12"),
                "invoice_date": fields.Date.from_string("2021-12-12"),
        }

        cls.invoice_1 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-12-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )
        
        cls.invoice_2 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-11-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 200}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )

        cls.invoice_3 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-10-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 300}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )

        cls.invoice_4 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-9-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 400}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )

        cls.invoice_5 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-8-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 500}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )

        cls.invoice_6 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-12-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )
        
        cls.invoice_7 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-11-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )

        cls.invoice_8 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-10-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )

        cls.invoice_9 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-9-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )

        cls.invoice_10 = cls.env["account.move"].create(
            {
                **invoice_data,
                "invoice_date_due": fields.Date.from_string("2021-8-30"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )

        cls.invoices = cls.env["account.move"].concat(cls.invoice_1, cls.invoice_2, cls.invoice_3, cls.invoice_4, cls.invoice_5)
        cls.invoices.action_post()

    @freeze_time('2022-01-04')
    def test_amount_of_each_period(self):
        expected_result = [
            (
                self.report.format_value(0, currency=self.curr_USD),    #Not Due
                self.report.format_value(100, currency=self.curr_USD),  #1-30
                self.report.format_value(200, currency=self.curr_USD),  #31-60
                self.report.format_value(300, currency=self.curr_USD),  #61-90
                self.report.format_value(400, currency=self.curr_USD),  #91-120
                self.report.format_value(500, currency=self.curr_USD),  #120+
                self.report.format_value(1500, currency=self.curr_USD)  #Total Amount
            )
        ]
        options = {"partner_id": self.partner_a.id}
        columns = [1, 2, 3, 4, 5, 6, 7]
        lines = self.report._get_summary_lines(options)
        self.assertLinesValues(lines, columns, expected_result)

    @freeze_time('2022-01-04')
    def test_not_due_amount(self):
        expected_result = [
            (
                self.report.format_value(1500, currency=self.curr_USD),    #Not Due
                self.report.format_value(1500, currency=self.curr_USD)  #Total Amount
            )
        ]
        move_lines = self.invoices.mapped("line_ids")
        move_lines.write({"date_maturity": fields.Date.from_string("2022-01-05")})
        options = {"partner_id": self.partner_a.id}
        columns = [1, 7]
        lines = self.report._get_summary_lines(options)
        self.assertLinesValues(lines, columns, expected_result)

    @freeze_time('2022-01-04')
    def test_not_due_amount_today(self):
        expected_result = [
            (
                self.report.format_value(1500, currency=self.curr_USD),    #Not Due
                self.report.format_value(1500, currency=self.curr_USD)  #Total Amount
            )
        ]
        today = fields.Date.today()
        move_lines = self.invoices.mapped("line_ids")
        move_lines.write({"date_maturity": today})
        options = {"partner_id": self.partner_a.id}
        columns = [1, 7]
        lines = self.report._get_summary_lines(options)
        self.assertLinesValues(lines, columns, expected_result)
    
    @freeze_time('2022-01-04')
    def test_amount_of_each_period_boundary(self):
        expected_result = [
            (
                self.report.format_value(400, currency=self.curr_USD),    #Not Due
                self.report.format_value(700, currency=self.curr_USD),  #1-30
                self.report.format_value(400, currency=self.curr_USD),  #31-60
                self.report.format_value(0, currency=self.curr_USD),  #61-90
                self.report.format_value(0, currency=self.curr_USD),  #91-120
                self.report.format_value(0, currency=self.curr_USD),  #120+
                self.report.format_value(1500, currency=self.curr_USD)  #Total Amount
            )
        ]
        dates = [
            fields.Date.from_string("2021-12-04"),
            fields.Date.from_string("2021-12-05"),
            fields.Date.from_string("2021-12-03"),
            fields.Date.from_string("2022-01-04"),
            fields.Date.from_string("2022-01-03")
        ]
        for idx, move in enumerate(self.invoices):
            move_lines = move.mapped("line_ids")
            move_lines.write({"date_maturity": dates[idx]})
        options = {"partner_id": self.partner_a.id}
        columns = [1, 2, 3, 4, 5, 6, 7]
        lines = self.report._get_summary_lines(options)
        self.assertLinesValues(lines, columns, expected_result)

    @freeze_time('2022-01-04')
    def test_amount_of_each_period_multi_currency(self):
        expected_result = [
            (
                self.report.format_value(0, currency=self.curr_EUR),    #Not Due
                self.report.format_value(100, currency=self.curr_EUR),  #1-30
                self.report.format_value(100, currency=self.curr_EUR),  #31-60
                self.report.format_value(100, currency=self.curr_EUR),  #61-90
                self.report.format_value(100, currency=self.curr_EUR),  #91-120
                self.report.format_value(100, currency=self.curr_EUR),  #120+
                self.report.format_value(500, currency=self.curr_EUR)  #Total Amount
            ),
            (
                self.report.format_value(0, currency=self.curr_USD),    #Not Due
                self.report.format_value(100, currency=self.curr_USD),  #1-30
                self.report.format_value(200, currency=self.curr_USD),  #31-60
                self.report.format_value(300, currency=self.curr_USD),  #61-90
                self.report.format_value(400, currency=self.curr_USD),  #91-120
                self.report.format_value(500, currency=self.curr_USD),  #120+
                self.report.format_value(1500, currency=self.curr_USD)  #Total Amount
            ),
        ]
        invoices_EUR = self.env["account.move"].concat(self.invoice_6, self.invoice_7, self.invoice_8, self.invoice_9, self.invoice_10)
        invoices_EUR.action_post()
        options = {"partner_id": self.partner_a.id}
        columns = [1, 2, 3, 4, 5, 6, 7]
        lines = self.report._get_summary_lines(options)
        self.assertLinesValues(list(filter(lambda line: line["class"] == "summary_values", lines)), columns, expected_result)
