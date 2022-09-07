from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import Form, tagged
from odoo import fields, Command

@tagged('post_install', '-at_install', 'basic_test')
class TestARInCharge(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super(TestARInCharge, cls).setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'test partner',
        })

        group_user = Command.link(cls.env['ir.model.data']._xmlid_to_res_id('base.group_user'))
        cls.internal_user = cls.env['res.users'].create({
            'name': 'test user', 
            'login': 'test user',
            'groups_id': [group_user]
        })

        cls.partner.ar_in_charge = cls.internal_user.id

    def test_auto_fill_ar_in_charge(self):
        """
        Test auto fill AR In Charge for invoice, credit note and payment
        """
        def init_move(move_type, partner=self.partner, date=fields.Date.from_string('2021-12-12'), invoice_date=fields.Date.from_string('2021-12-12')):
            move_form = Form(self.env['account.move'].with_context(default_move_type=move_type))
            move_form.date = date
            move_form.invoice_date = invoice_date
            move_form.partner_id = partner
            return move_form.save()
        
        def init_payment(partner_type, payment_type, partner=self.partner, date=fields.Date.from_string('2021-12-12')):
            payment_form = Form(self.env['account.payment'])
            payment_form.partner_type = partner_type
            payment_form.payment_type = payment_type
            payment_form.date = date
            payment_form.partner_id = partner
            payment_form.payment_method_line_id = self.inbound_payment_method_line
            return payment_form.save()

        invoice = init_move('in_invoice')
        credit_note = init_move('out_refund')
        payment = init_payment('customer', 'inbound')
    
        self.assertEqual(invoice.ar_in_charge, self.internal_user)
        self.assertEqual(credit_note.ar_in_charge, self.internal_user)
        self.assertEqual(payment.ar_in_charge, self.internal_user)
    
    def test_domain_ar_in_charge(self):
        """
        Test domain AR In Charge
        """
        domain = [('share', '=', False)]
        group_public = Command.link(self.env['ir.model.data']._xmlid_to_res_id('base.group_public'))
        external_user = self.env['res.users'].create({
            'name': 'external user', 
            'login': 'external user',
            'groups_id': [group_public]
        })

        internal_users = self.env['res.users'].search(domain)
        self.assertTrue(self.internal_user in internal_users)
        self.assertFalse(external_user in internal_users)

