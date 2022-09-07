from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestInvoicingCommonBatchAdjustment(AccountTestInvoicingCommon):

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

        # Bank journals
        cls.bank_journal_usd = cls.company_data['default_journal_bank']
        cls.bank_journal_eur = cls.env['account.journal'].create({
            'name': 'Bank EUR',
            'type': 'bank',
            'code': 'BNK80',
            'currency_id': cls.curr_eur.id,
            'company_id': cls.company.id
        })

        # Outstanding accounts from setting
        cls.payment_debit_account = cls.company.account_journal_payment_debit_account_id
        cls.payment_credit_account = cls.company.account_journal_payment_credit_account_id

        # Payment method
        cls.manual_in_method = cls.env.ref('account.account_payment_method_manual_in')
        cls.manual_out_method = cls.env.ref('account.account_payment_method_manual_out')

        # Create assets account
        cls.account_asset_1 = cls.copy_account(cls.company_data['default_account_assets'])
        cls.account_asset_2 = cls.copy_account(cls.company_data['default_account_assets'])

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
