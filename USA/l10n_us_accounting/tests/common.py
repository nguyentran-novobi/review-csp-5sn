from odoo import Command
from odoo.tests.common import Form
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestInvoicingCommonUSAccounting(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company = cls.company_data['company']
        # Set up Rounding for USD currency
        cls.company_data['currency'].write({'rounding': 0.01})
        # Set up Rounding and Rate for EUR currency
        cls.curr_eur = cls.env.ref('base.EUR')
        cls.curr_eur.write({
            'active': True,
            'rounding': 0.01
        })

    @classmethod
    def create_invoice(cls, move_type='out_invoice', date=None, amount=0.0, partner_id=None, currency_id=None,
                       company_id=None, auto_validate=False):
        """
        Helper: create new invoice/bill and post it if needed
        """
        invoice_values = {
            'move_type': move_type,
            'partner_id': partner_id,
            'invoice_date': date,
            'invoice_line_ids': [Command.create({'name': '/', 'price_unit': amount})]
        }
        if currency_id:
            invoice_values['currency_id'] = currency_id
        if company_id:
            invoice_values['company_id'] = company_id

        new_invoice = cls.env['account.move'].create(invoice_values)
        if auto_validate:
            new_invoice.action_post()

        return new_invoice

    @classmethod
    def create_customer_invoice(cls, date=None, amount=0.0, partner_id=None, currency_id=None,
                                company_id=None, auto_validate=False):
        return cls.create_invoice(date=date, amount=amount, partner_id=partner_id, currency_id=currency_id,
                                  company_id=company_id, auto_validate=auto_validate)

    @classmethod
    def create_vendor_bill(cls, date=None, amount=0.0, partner_id=None, currency_id=None,
                           company_id=None, auto_validate=False):
        return cls.create_invoice(move_type='in_invoice', date=date, amount=amount, partner_id=partner_id,
                                  currency_id=currency_id, company_id=company_id, auto_validate=auto_validate)

    @classmethod
    def create_payment(cls, payment_type='inbound', partner_type='customer', amount=0.0, partner_id=None, date=None,
                       currency_id=None, company_id=None, auto_validate=False, **other_values):
        """
        Helper: create new account.payment and post it if needed
        """
        payment_values = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'amount': amount,
            'partner_id': partner_id,
        }
        if date:
            payment_values['date'] = date
        if currency_id:
            payment_values['currency_id'] = currency_id
        if company_id:
            payment_values['company_id'] = company_id
        payment_values.update(other_values)

        new_payment = cls.env['account.payment'].create(payment_values)
        if auto_validate:
            new_payment.action_post()

        return new_payment

    @classmethod
    def create_customer_payment(cls, partner_id=None, amount=0.0, date=None, currency_id=None, company_id=None,
                                auto_validate=False):
        return cls.create_payment(partner_id=partner_id, amount=amount, date=date, currency_id=currency_id,
                                  company_id=company_id, auto_validate=auto_validate)

    @classmethod
    def create_vendor_payment(cls, partner_id=None, amount=0.0, date=None, currency_id=None, company_id=None,
                              auto_validate=False):
        return cls.create_payment(payment_type='outbound', partner_type='supplier', partner_id=partner_id, amount=amount,
                                  date=date, currency_id=currency_id, company_id=company_id, auto_validate=auto_validate)

    def _reconcile_invoice_and_payments(self, invoice, payment_moves):
        if invoice.move_type == 'out_invoice':
            payment_lines = payment_moves.mapped('line_ids').filtered(lambda r: r.credit > 0)
        else:
            payment_lines = payment_moves.mapped('line_ids').filtered(lambda r: r.debit > 0)
        for line in payment_lines:
            invoice.js_assign_outstanding_line(line.id)

    @classmethod
    def create_new_session(cls,journal, beginning_balance, ending_balance, statement_ending_date='2022-02-22'):
        action = journal.action_usa_reconcile()
        context = action['context']
        new_session_form = Form(cls.env['account.bank.reconciliation.data'].with_context(context), 'l10n_us_accounting.bank_reconciliation_data_popup_form')
        new_session_form.beginning_balance = beginning_balance
        new_session_form.ending_balance = ending_balance
        new_session_form.statement_ending_date = statement_ending_date
        new_session = new_session_form.save()
        return new_session
