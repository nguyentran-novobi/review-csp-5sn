# -*- coding: utf-8 -*-
from .common import TestInvoicingCommonUSAccounting

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import Form
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'basic_test')
class TestWriteOff(TestInvoicingCommonUSAccounting):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.invoice_a = cls.init_invoice('out_invoice', products=cls.product_a, invoice_date='2022-01-01', post=True)
        cls.invoice_b = cls.init_invoice('out_invoice', products=cls.product_a, invoice_date='2022-01-01')

        cls.write_off_a = cls.env['account.invoice.refund.usa'].with_context(
            default_currency_id=cls.invoice_a.currency_id.id,
            active_model="account.move",
            active_ids=cls.invoice_a.ids).create({
                'account_id': cls.product_a.property_account_income_id.id,
                'reason': 'Test Write Off',
                'write_off_amount': 1.0
            })

    def test_create_negative_write_off_form(self):
        with self.assertRaises(ValidationError):
            self.write_off_a.write_off_amount = -100.0

    def test_create_write_off_form(self):
        self.write_off_a.write_off_amount = 321.0

        write_off_action_result = self.write_off_a.action_write_off()
        write_off_a = self.env['account.move'].browse(write_off_action_result['res_id'])

        self.assertInvoiceValues(write_off_a, [
            {
                'product_id': False,
                'price_unit': 321.0,
                'price_subtotal': 321.0,
                'price_total': 321.0,
                'quantity': 1.0,
                'account_id': self.product_a.property_account_income_id.id,
                'name': 'Write Off',
                'currency_id': self.invoice_a.currency_id.id,
                'debit': 321.0,
                'credit': 0.0,
            },
            {
                'product_id': False,
                'price_unit': -321.0,
                'price_subtotal': -321.0,
                'price_total': -321.0,
                'quantity': 1.0,
                'name': '',
                'account_id': self.company_data['default_account_receivable'].id,
                'currency_id': self.invoice_a.currency_id.id,
                'debit': 0.0,
                'credit': 321.0,
            },
        ], {
            'currency_id': self.invoice_a.currency_id.id,
            'amount_untaxed': 321.0,
            'amount_total': 321.0,
            'state': 'draft'
        })

        self.assertEqual(write_off_a.date, fields.Date.today())

    def test_create_and_apply_write_off_form(self):
        self.write_off_a.write_off_amount = 321.0

        write_off_action_result = self.write_off_a.with_context(create_and_apply=True).action_write_off()
        write_off_a = self.env['account.move'].browse(write_off_action_result['res_id'])

        self.assertInvoiceValues(write_off_a, [
            {
                'product_id': False,
                'price_unit': 321.0,
                'price_subtotal': 321.0,
                'price_total': 321.0,
                'quantity': 1.0,
                'account_id': self.product_a.property_account_income_id.id,
                'name': 'Write Off',
                'currency_id': self.invoice_a.currency_id.id,
                'debit': 321.0,
                'credit': 0.0,
            },
            {
                'product_id': False,
                'price_unit': -321.0,
                'price_subtotal': -321.0,
                'price_total': -321.0,
                'quantity': 1.0,
                'name': '',
                'account_id': self.company_data['default_account_receivable'].id,
                'currency_id': self.invoice_a.currency_id.id,
                'debit': 0.0,
                'credit': 321.0,
            },
        ], {
            'currency_id': self.invoice_a.currency_id.id,
            'amount_untaxed': 321.0,
            'amount_total': 321.0,
            'state': 'posted'
        })

        self.assertEqual(self.invoice_a.amount_residual, 829.0)
        self.assertEqual(write_off_a.date, fields.Date.today())

    def test_create_write_off_unqualified_invoice_tree(self):
        # Unqualified Invoices: fully paid and haven't posted yet
        invoices = self.invoice_a + self.invoice_b
        # Use write off to make invoice_a fully paid
        self.write_off_a.write_off_amount = 1150
        self.write_off_a.with_context(create_and_apply=True).action_write_off()
        # Open write off in tree view
        with self.assertRaises(ValidationError):
            invoices.action_open_write_off_popup()

    def test_create_incorrect_write_off_invoice_tree(self):
        self.invoice_b.action_post()
        invoices = self.invoice_a + self.invoice_b
        action = invoices.action_open_write_off_popup()
        multiple_writeoff_wizard = self.env[action['res_model']].create({
            'move_ids': action['context']['default_move_ids'],
            'move_type': action['context']['default_move_type']
        })
        # Discount Amount must be positive and cannot be bigger than Amount Due.
        for line in multiple_writeoff_wizard.move_ids:
            # discount_type is value
            with self.assertRaises(ValidationError):
                line_form = Form(line)
                line_form.value = -112.00
                line_form.save()
            with self.assertRaises(ValidationError):
                line_form = Form(line)
                line_form.value = line.amount_residual + 0.01
                line_form.save()
            # discount_type is percentage
            with self.assertRaises(ValidationError):
                line_form = Form(line)
                line_form.discount_type = 'percentage'
                line_form.value = -1
                line_form.save()
            with self.assertRaises(ValidationError):
                line_form = Form(line)
                line_form.discount_type = 'percentage'
                line_form.value = 101
                line_form.save()

    def test_create_write_off_invoice_tree(self):
        self.invoice_b.action_post()
        invoices = self.invoice_a + self.invoice_b
        action = invoices.action_open_write_off_popup()
        multiple_writeoff_wizard = self.env[action['res_model']].create({
            'move_ids': action['context']['default_move_ids'],
            'move_type': action['context']['default_move_type']
        })
        line_1_form = Form(multiple_writeoff_wizard.move_ids[0])
        line_1_form.value = 321.0
        line_1_form.save()
        line_2_form = Form(multiple_writeoff_wizard.move_ids[1])
        line_2_form.discount_type = 'percentage'
        line_2_form.value = 50
        line_2_form.save()

        multiple_writeoff_wizard_result = multiple_writeoff_wizard.action_write_off()
        write_off_list = multiple_writeoff_wizard_result['domain'][0][2]
        write_offs = self.env['account.move'].browse(write_off_list)
        self.assertEqual(write_offs[0].amount_residual, 321.0)
        self.assertEqual(write_offs[1].amount_residual, 575.0)

    def test_create_and_apply_write_off_invoice_tree(self):
        self.invoice_b.action_post()
        invoices = self.invoice_a + self.invoice_b
        action = invoices.action_open_write_off_popup()
        multiple_writeoff_wizard = self.env[action['res_model']].create({
            'move_ids': action['context']['default_move_ids'],
            'move_type': action['context']['default_move_type']
        })
        line_1_form = Form(multiple_writeoff_wizard.move_ids[0])
        line_1_form.value = 321.0
        line_1_form.save()
        line_2_form = Form(multiple_writeoff_wizard.move_ids[1])
        line_2_form.discount_type = 'percentage'
        line_2_form.value = 50
        line_2_form.save()

        multiple_writeoff_wizard_result = multiple_writeoff_wizard.with_context(create_and_apply=True).action_write_off()
        write_off_list = multiple_writeoff_wizard_result['domain'][0][2]
        write_offs = self.env['account.move'].browse(write_off_list)
        self.assertEqual(write_offs[0].amount_total, 321.0)
        self.assertEqual(self.invoice_a.amount_residual, 829.0)
        self.assertEqual(write_offs[1].amount_total, 575.0)
        self.assertEqual(self.invoice_b.amount_residual, 575.0)