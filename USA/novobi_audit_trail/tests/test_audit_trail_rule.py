from odoo.tests.common import tagged, Form
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
@tagged('post_install', '-at_install', 'basic_test')
class TestAuditTrailRule(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super(TestAuditTrailRule, cls).setUpClass()

    def test_unique_rule_per_model(self):
        try:
            new_rule = self.env['audit.trail.rule'].create({
                'model_id': self.env.ref('account.model_account_move').id
            })
        except ValidationError as error:
            self.assertEqual(error.args[0], "A tracking model must have only one tracking rule.")
    
    def test_onchange_model_id(self):
        rule_form = Form(self.env["audit.trail.rule"])
        rule_form.model_id = self.env.ref("sale.model_sale_order")
        rule_form.parent_field_id = self.env.ref("sale.field_sale_order__analytic_account_id")
        rule_form.tracking_field_ids.add = self.env.ref("sale_stock.field_sale_order__warehouse_id")
        rule_form.model_id = self.env.ref("base.model_res_partner")
        self.assertFalse(rule_form.tracking_field_ids)
