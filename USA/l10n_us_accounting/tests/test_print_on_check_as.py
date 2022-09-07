from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import Form, tagged
from odoo import fields


@tagged("post_install", "-at_install", "basic_test")
class TestPrintOnCheckAs(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super(TestPrintOnCheckAs, cls).setUpClass()

        cls.partner_a.name = "Default Name"
        bank_journal = cls.company_data["default_journal_bank"]
        cls.payment_method_line_check = bank_journal.outbound_payment_method_line_ids.filtered(lambda line: line.code == "check_printing")

    def test_default_name_on_check(self):
        """
        Test get default name on check when active "Print On Check" checkbox
        """
        expected_name = "Default Name"
        contact_form = Form(self.partner_a)
        contact_form.print_check_as = True
        self.assertEqual(contact_form.check_name, expected_name)

    def test_get_default_check_name(self):
        """
        Test get default name and name on check when printing check
        """
        expected_default_name = "Default Name"
        expected_name = "Name Print On Check"
        payment = self.env["account.payment"].create(
            {
                "partner_id": self.partner_a.id,
                "payment_type": "outbound",
                "date": fields.Date.from_string("2022-01-01"),
                "payment_method_line_id": self.payment_method_line_check.id,
            }
        )
        default_name_on_check = self._get_name_on_check(payment)
        self.assertEqual(default_name_on_check, expected_default_name)
        # Update the name on check
        contact_form = Form(self.partner_a)
        contact_form.print_check_as = True
        contact_form.check_name = expected_name
        contact_form.save()
        name_on_check = self._get_name_on_check(payment)
        self.assertEqual(name_on_check, expected_name)

    def _get_name_on_check(self, payment):
        stub_pages = payment._check_make_stub_pages() or [False]
        check_info = payment._check_build_page_info(0, stub_pages[0])
        return check_info["partner_name"]
