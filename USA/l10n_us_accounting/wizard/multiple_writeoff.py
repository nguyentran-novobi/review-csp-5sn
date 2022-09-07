# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from ..utils.writeoff_utils import write_off

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class MultipleWriteOffWizard(models.TransientModel):
    _name = "multiple.writeoff.wizard"
    _description = "Create Write-off for multiple invoices/bills"

    move_ids = fields.One2many("multiple.writeoff.wizard.line", "writeoff_wizard_id")
    move_type = fields.Char()

    def action_write_off(self):

        is_apply = self.env.context.get('create_and_apply', False)

        refund_list = []
        for form in self:
            for wizard_line in form.move_ids:
                inv = wizard_line.move_id
                refund_list.append(write_off(inv, wizard_line, is_apply).id)

        return {
            'name': _('Created Write-offs'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('id', 'in', refund_list)],
        }


class MultipleWriteOffWizardLine(models.TransientModel):
    _name = "multiple.writeoff.wizard.line"
    _description = "Multiple Writeoff Wizard Line"

    @api.model
    def _default_bad_debt_account_id(self):
        company_id = self.company_id
        move_type = self.move_id.move_type
        if move_type == "out_invoice" and company_id.bad_debt_account_id:
            return company_id.bad_debt_account_id.id
        elif move_type == "in_invoice" and company_id.bill_bad_debt_account_id:
            return company_id.bill_bad_debt_account_id.id
        return False

    writeoff_wizard_id = fields.Many2one("multiple.writeoff.wizard")
    move_id = fields.Many2one("account.move", string="Bill/Invoice", ondelete="cascade")
    name = fields.Char(string='Number', related="move_id.name")
    invoice_origin = fields.Char(string="Source Document", related="move_id.invoice_origin")
    invoice_date = fields.Date(string='Bill/Invoice Date', related="move_id.invoice_date")
    invoice_date_due = fields.Date(string='Due Date', related="move_id.invoice_date_due")
    amount_total = fields.Monetary(string='Total', related="move_id.amount_total",
                                   currency_field='currency_id')
    amount_residual = fields.Monetary(string='Amount Due', related="move_id.amount_residual",
                                      currency_field='currency_id')
    company_id = fields.Many2one('res.company', 'Company', related="move_id.company_id")
    currency_id = fields.Many2one('res.currency', 'Currency', related="move_id.currency_id")
    account_id = fields.Many2one("account.account", string='Write-off Account',
                                 default=_default_bad_debt_account_id,
                                 domain=[('deprecated', '=', False)])
    reason = fields.Char(string='Reason')
    date = fields.Date(string='Write-off Date',
                       default=fields.Date.context_today)
    discount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Amount Due')
    ], default='fixed', required=True, string='Discount Type')
    value = fields.Float("Value")
    write_off_amount = fields.Monetary(
        'Discount Amount',
        currency_field='currency_id',
        compute='_compute_discount_amount',
        readonly=True,
        required=True)

    @api.onchange('discount_type')
    def _onchange_value(self):
        for rec in self:
            rec.value = 100.0 if rec.discount_type == 'percentage' else rec.amount_residual

    @api.depends('value')
    def _compute_discount_amount(self):
        for rec in self:
            amount = rec.amount_residual * rec.value / \
                100.0 if rec.discount_type == 'percentage' else rec.value
            if rec._check_valid_value(amount, rec.amount_residual, rec.currency_id):
                rec.write_off_amount = amount
            else:
                raise ValidationError(
                    'Discount Amount must be positive and cannot be bigger than Amount Due.')

    def _check_valid_value(self, amount, amount_residual, currency):
        if currency.compare_amounts(amount, 0.00) <= 0 or currency.compare_amounts(amount, amount_residual) > 0:
            return False
        return True
