from odoo import Command
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.addons.account_partner_deposit.tests.common import AccountTestInvoicingCommonDeposit


class TestSaleDepositCommon(TestSaleCommon, AccountTestInvoicingCommonDeposit):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # Create EUR pricelist
        cls.pricelist_eur = cls.env['product.pricelist'].create({
            'name': 'EUR',
            'currency_id': cls.env.ref('base.EUR').id
        })

        # Create SO
        sale_order_model = cls.env['sale.order'].with_context(tracking_disable=True)
        cls.sale_order = sale_order_model.create({
            'partner_id': cls.partner_a.id,
            'partner_invoice_id': cls.partner_a.id,
            'partner_shipping_id': cls.partner_a.id,
            'pricelist_id': cls.company_data['default_pricelist'].id,
            'order_line': [
                Command.create({
                    'name': cls.company_data['product_delivery_no'].name,
                    'product_id': cls.company_data['product_delivery_no'].id,
                    'product_uom_qty': 1,
                    'product_uom': cls.company_data['product_delivery_no'].uom_id.id,
                    'price_unit': 500.64,
                    'tax_id': False
                })
            ]
        })
        cls.sale_order.action_confirm()

        # Create Make a deposit wizard
        context = {
            'active_model': 'sale.order',
            'active_id': cls.sale_order.id,
            'default_currency_id': cls.sale_order.currency_id.id
        }
        cls.make_a_deposit_wiz = cls.env['order.make.deposit'].with_context(context).create({})
