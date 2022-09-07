# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class TransactionLine(models.Model):
    _name = "recurring.transaction.line"
    _description = "Recurring Transaction Line"

    name = fields.Char('Label')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    partner_id = fields.Many2one('res.partner', 'Partner')
    move_id = fields.Many2one('recurring.transaction', 'Transaction')
    currency_id = fields.Many2one('res.currency', related='move_id.currency_id')
    company_id = fields.Many2one('res.company', related='move_id.company_id')
    debit = fields.Monetary(string='Debit', default=0.0, currency_field='currency_id')
    credit = fields.Monetary(string='Credit', default=0.0, currency_field='currency_id')
    transaction_type = fields.Selection(related='move_id.transaction_type')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity',
                            default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    tax_ids = fields.Many2many('account.tax', string='Taxes', check_company=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', check_company=True)
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags', check_company=True)
    price_subtotal = fields.Float(compute='_compute_amount', string='Subtotal', digits='Account', store=True)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False, help="Technical field for UX purpose.")

    @api.onchange('product_id')
    def _onchange_product(self):
        for line in self:
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue

            line.name = line._get_computed_name()
            line.account_id = line._get_computed_account()

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for line in self:
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue
            if float_compare(line.quantity, 0, precision_rounding=line.product_id.uom_id.rounding) <= 0:
                raise ValidationError(_('Quantity must be positive.'))
            if float_compare(line.price_unit, 0, precision_rounding=line.move_id.currency_id.rounding) < 0:
                raise ValidationError(_('Unit Price must not be negative.'))
            line.price_subtotal = line.quantity * line.price_unit

    def _get_computed_name(self):
        self.ensure_one()
        if not self.product_id:
            return ''

        product = self.product_id
        values = []
        if product.partner_ref:
            values.append(product.partner_ref)
        if self.transaction_type == 'customer_invoice' and product.description_sale:
            values.append(product.description_sale)
        elif self.transaction_type == 'vendor_bill' and product.description_purchase:
            values.append(product.description_purchase)
        return '\n'.join(values)

    def _get_computed_account(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        if not self.product_id:
            return

        accounts = self.product_id.product_tmpl_id.get_product_accounts()
        if self.transaction_type == 'customer_invoice':
            return accounts['income'] or self.account_id
        elif self.transaction_type == 'vendor_bill':
            return accounts['expense'] or self.account_id
