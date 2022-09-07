from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged
from odoo import fields, Command

@tagged("post_install", "-at_install", "basic_test")
class TestPendingBillableExpenseReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super(TestPendingBillableExpenseReport, cls).setUpClass()

        cls.curr_USD = cls.env.ref("base.USD")
        cls.curr_EUR = cls.env.ref("base.EUR")

        # ==== Bill/PO ====

        cls.bill = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.partner_a.id,
                "date": fields.Date.from_string("2021-12-12"),
                "invoice_date": fields.Date.from_string("2021-12-12"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 100}),
                ],
                "currency_id": cls.curr_USD.id,
            }
        )

        cls.bill.action_post()
        cls.bill.open_expense_popup()
        cls.bill_expenses = cls.bill.billable_expenses_ids

        cls.po = cls.env["purchase.order"].create(
            {
                "partner_id": cls.partner_b.id,
                "date_order": fields.Date.from_string("2021-12-30"),
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product_a.id,
                            "product_qty": 1,
                            "price_unit": 200,
                        }
                    ),
                ],
                "currency_id": cls.curr_EUR.id,
            }
        )

        cls.po.open_expense_popup()
        cls.po_expenses = cls.po.billable_expenses_ids
        cls.report = cls.env["billable.expense.report"]

        cls.invoice = cls.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": cls.partner_b.id,
            "date": fields.Date.from_string("2021-12-12"),
            "invoice_date": fields.Date.from_string("2021-12-12"),
        })

    def assign_expenses(self, apply_to_invoice = False):
        self.bill_expenses.write({"customer_id": self.partner_b.id})
        self.po_expenses.write({"customer_id": self.partner_a.id})
        if apply_to_invoice:
            res = self.invoice.from_expense_to_invoice(self.bill_expenses.ids, "item")

    def assertReportLines(self, columns, expected_lines, options, apply_to_invoice = False):
        self.assign_expenses(apply_to_invoice)
        lines = self.report._get_lines(options, None)
        self.assertLinesValues(lines, columns, expected_lines)

    def test_group_by_partner(self):
        """
        Test group by partner function
        """
        expected_result = {
            self.curr_EUR: {
                self.partner_a: {
                    "lines": [self.po_expenses[0]],
                    "amount": 200.0,
                }
            },
            self.curr_USD: {
                self.partner_b: {
                    "lines": [self.bill_expenses[0]],
                    "amount": 100.0,
                }
            },
        }
        self.bill_expenses.write({"customer_id": self.partner_b.id})
        self.po_expenses.write({"customer_id": self.partner_a.id})
        groups = self.report.group_by_partner_id({"include_po": True}, None)
        self.assertDictEqual(groups, expected_result)

    def test_report_lines_without_applying_to_invoice(self):
        """
        Test report lines without applying invoice
        """
        expected_result = [
            ["partner_a", "", "", "", "", "200.00 €", ""],
            [self.po.name, "12-30-2021", "Payable Invoice", "partner_b", "product_a", "200.00 €", False],
            ["Total", "", "", "", "", "200.00 €", ""],
            ["", "", "", "", "", "", ""],
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", False],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        options = {"include_po": True, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options)

    def test_report_lines_with_applying_to_invoice(self):
        """
        Test report lines with applying invoice
        """
        expected_result = [
            ["partner_a", "", "", "", "", "200.00 €", ""],
            [self.po.name, "12-30-2021", "Payable Invoice", "partner_b", "product_a", "200.00 €", False],
            ["Total", "", "", "", "", "200.00 €", ""],
            ["", "", "", "", "", "", ""],
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", True],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        options = {"include_po": True, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options, apply_to_invoice=True)

    def test_report_lines_with_po_has_bill(self):
        """
        Test report lines when po has bill
        """
        self.po_expenses.write({"customer_id": self.partner_a.id})
        self.po.button_confirm()
        picking = self.po.picking_ids
        move_line = picking.move_lines
        move_line.quantity_done = move_line.product_uom_qty
        picking.with_context(skip_immediate=True).button_validate()
        res = self.po.action_create_invoice()
        bill = self.po.invoice_ids
        bill.write({
            "partner_id": self.partner_b.id,
            "invoice_date": fields.Date.from_string("2021-12-30"),
            "date": fields.Date.from_string("2021-12-30")
            })
        bill.action_post()
        expected_result = [
            ["partner_a", "", "", "", "", "200.00 €", ""],
            [bill.name, "12-30-2021", "Payable Invoice", "partner_b", "product_a", "200.00 €", False],
            ["Total", "", "", "", "", "200.00 €", ""],
            ["", "", "", "", "", "", ""],
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", False],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        options = {"include_po": True, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options)

    def test_report_lines_with_cancelled_bill_po(self):
        """
        Test report lines when po has cancelled bill
        """
        self.po_expenses.write({"customer_id": self.partner_a.id})
        self.po.button_confirm()
        picking = self.po.picking_ids
        move_line = picking.move_lines
        move_line.quantity_done = move_line.product_uom_qty
        picking.with_context(skip_immediate=True).button_validate()
        res = self.po.action_create_invoice()
        bill = self.po.invoice_ids
        bill.write({
            "partner_id": self.partner_b.id,
            "invoice_date": fields.Date.from_string("2021-12-30"),
            "date": fields.Date.from_string("2021-12-30")
            })
        bill.action_post()
        bill.button_draft()
        expected_result = [
            ["partner_a", "", "", "", "", "200.00 €", ""],
            [self.po.name, "12-30-2021", "Payable Invoice", "partner_b", "product_a", "200.00 €", False],
            ["Total", "", "", "", "", "200.00 €", ""],
            ["", "", "", "", "", "", ""],
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", False],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        
        options = {"include_po": True, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options)
    
    def test_include_purchase_order_filter_active(self):
        """
        Test active include po filter
        """
        expected_result = [
            ["partner_a", "", "", "", "", "200.00 €", ""],
            [self.po.name, "12-30-2021", "Payable Invoice", "partner_b", "product_a", "200.00 €", False],
            ["Total", "", "", "", "", "200.00 €", ""],
            ["", "", "", "", "", "", ""],
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", True],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        options = {"include_po": True, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options, apply_to_invoice=True)
    
    def test_include_purchase_order_filter_inactive(self):
        """
        Test inactive include po filter
        """
        expected_result = [
            ["partner_b", "", "", "", "", "$ 100.00", ""],
            [self.bill.name, "12-12-2021", "Payable Invoice", "partner_a", "/", "$ 100.00", True],
            ["Total", "", "", "", "", "$ 100.00", ""],
            ["", "", "", "", "", "", ""],
        ]
        options = {"include_po": False, "unfolded_lines": [], "unfold_all": True}
        columns = [0,1,2,3,4,5,6]
        self.assertReportLines(columns, expected_result, options, apply_to_invoice=True)

    def test_bill_po_date(self):
        """
        Test bill/po date column 
        """
        expected_result = [
            [self.po.date_order.strftime("%m-%d-%Y")],
            [self.bill.invoice_date_due.strftime("%m-%d-%Y")],
        ]
        self.assign_expenses(apply_to_invoice=True)
        lines = list(filter(lambda l: l["name"] in [self.po.name, self.bill.name], self.report._get_lines({"include_po": True, "unfolded_lines": [], "unfold_all": True}, None)))
        self.assertLinesValues(lines, [1], expected_result)

    def test_supplier(self):
        """
        Test supplier column
        """
        expected_result = [
            [self.po.partner_id.name],
            [self.bill.partner_id.name],
        ]
        self.assign_expenses(apply_to_invoice=True)
        lines = list(filter(lambda l: l["name"] in [self.po.name, self.bill.name], self.report._get_lines({"include_po": True, "unfolded_lines": [], "unfold_all": True}, None)))
        self.assertLinesValues(lines, [3], expected_result)
    
    def test_description(self):
        """
        Test description column
        """
        expected_result = [
            [self.po_expenses.description],
            [self.bill_expenses.description],
        ]
        self.assign_expenses(apply_to_invoice=True)
        lines = list(filter(lambda l: l["name"] in [self.po.name, self.bill.name], self.report._get_lines({"include_po": True, "unfolded_lines": [], "unfold_all": True}, None)))
        self.assertLinesValues(lines, [4], expected_result)

    def test_markup(self):
        """
        Test amount column
        """
        expected_result = [
            [self.report.format_value(self.po_expenses.amount_total, currency=self.po.currency_id)],
            [self.report.format_value(self.bill_expenses.amount_total, currency=self.bill.currency_id)],
        ]
        self.assign_expenses(apply_to_invoice=True)
        lines = list(filter(lambda l: l["name"] in [self.po.name, self.bill.name], self.report._get_lines({"include_po": True, "unfolded_lines": [], "unfold_all": True}, None)))
        self.assertLinesValues(lines, [5], expected_result)

    def test_total_amount_currency(self):
        """
        Test total currency
        """
        expected_result = [
            [self.report.format_value(200, currency=self.po.currency_id)],
            [self.report.format_value(250, currency=self.bill.currency_id)],
        ]
        partner_c = self.env["res.partner"].create({
            "name": "partner_c",
        })
        new_bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner_c.id,
                "date": fields.Date.from_string("2021-12-12"),
                "invoice_date": fields.Date.from_string("2021-12-12"),
                "invoice_line_ids": [
                    Command.create({"name": "/", "price_unit": 150}),
                ],
                "currency_id": self.curr_USD.id,
            }
        )
        new_bill.action_post()
        new_bill.open_expense_popup()
        new_bill.billable_expenses_ids.write({"customer_id": self.partner_b.id})
        self.assign_expenses(apply_to_invoice=True)
        lines = list(filter(lambda l: l["name"] == "Total", self.report._get_lines({"include_po": True, "unfolded_lines": [], "unfold_all": True}, None)))
        self.assertLinesValues(lines, [5], expected_result)

    



