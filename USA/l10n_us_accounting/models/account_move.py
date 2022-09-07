# Copyright © 2022 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError, UserError

class AccountMoveUSA(models.Model):
    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _build_invoice_line_item(self, write_off_amount, account_id, line_ids, reconcile_account_id, reverse_type):
        new_invoice_line_ids = {}
        if line_ids:
            debit_wo, credit_wo = (0, write_off_amount) if reverse_type == 'in_refund' else (write_off_amount, 0)

            new_invoice_line_ids = {
                'name': 'Write Off',
                'display_name': 'Write Off',
                'product_uom_id': False,
                'account_id': account_id,
                'quantity': 1.0,
                'price_unit': write_off_amount,
                'product_id': False,
                'discount': 0.0,
                'debit': debit_wo,
                'credit': credit_wo
            }

        return [Command.create(new_invoice_line_ids)]


    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    ar_in_charge = fields.Many2one(string='AR In Charge', comodel_name='res.users', domain=[('share', '=', False)])
    is_payment_receipt = fields.Boolean('Is Payment Receipt?', related='payment_id.is_payment_receipt')

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    @api.onchange('partner_id')
    def _onchange_select_customer(self):
        self.ar_in_charge = self.partner_id.ar_in_charge

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def button_draft_usa(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_accounting.action_view_button_set_to_draft_message').read()[0]
        action['context'] = isinstance(action.get('context', {}), dict) or {}
        action['context']['default_move_id'] = self.id
        return action

    def create_refund(self, write_off_amount, company_currency_id, account_id, invoice_date=None, description=None,
                      journal_id=None):
        new_invoices = self.browse()
        for invoice in self:
            # Copy from Odoo
            reverse_type_map = {
                'entry': 'entry',
                'out_invoice': 'out_refund',
                'out_refund': 'entry',
                'in_invoice': 'in_refund',
                'in_refund': 'entry',
                'out_receipt': 'entry',
                'in_receipt': 'entry',
            }
            reconcile_account_id = invoice.partner_id.property_account_receivable_id \
                if invoice.is_sale_document(include_receipts=True) else invoice.partner_id.property_account_payable_id
            reverse_type = reverse_type_map[invoice.move_type]

            default_values = {
                'ref': description,
                'date': invoice_date,
                'invoice_date': invoice_date,
                'invoice_date_due': invoice_date,
                'journal_id': journal_id,
                'invoice_payment_term_id': None,
                'move_type': reverse_type,
                'invoice_origin': invoice.name,
                'state': 'draft'
            }
            values = invoice._reverse_move_vals(default_values, False)

            line_ids = values.pop('line_ids')
            if 'invoice_line_ids' in values:
                values.pop('invoice_line_ids')
            new_invoice_line_ids = self._build_invoice_line_item(abs(write_off_amount), account_id.id, line_ids, reconcile_account_id, reverse_type)

            refund_invoice = self.create(values)
            refund_invoice.write({'invoice_line_ids': new_invoice_line_ids})

            # Create message post
            message = 'This write off was created from ' \
                      '<a href=# data-oe-model=account.move data-oe-id={}>{}</a>'.format(invoice.id, invoice.name)
            refund_invoice.message_post(body=message)

            new_invoices += refund_invoice
        return new_invoices

    def button_write_off(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("l10n_us_accounting.action_account_write_off_bad_debt_usa")
        return action

    def action_open_write_off_popup(self):
        moves_lst = []
        for move in self:
            if not (move.state != 'posted' or move.currency_id.compare_amounts(move.amount_residual, 0.00) <= 0):
                moves_lst.append(move)
        if not len(moves_lst):
            raise ValidationError(_('There is nothing left to create write-offs.'))

        return {
            'name': _('Create Write-off'),
            'type': 'ir.actions.act_window',
            'res_model': 'multiple.writeoff.wizard',
            'context': {
                'default_move_ids': [Command.create({'move_id': move.id, 'value': move.amount_residual}) for move in moves_lst],
                'default_move_type': self[0].move_type,
            },
            'view_mode': 'form',
            'target': 'new',
        }

    def button_draft_usa(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("l10n_us_accounting.action_view_button_set_to_draft_message")
        action['context'] = isinstance(action.get('context', {}), dict) or {}
        action['context']['default_move_id'] = self.id
        return action

    def _get_reconciled_info_JSON_values(self):
        """
        Override
        Add label of applied transactions to dict values to show in payment widget on invoice form
        """
        reconciled_vals = super(AccountMoveUSA, self)._get_reconciled_info_JSON_values()

        for val in reconciled_vals:
            move_id = self.browse(val.get('move_id'))
            if val.get('account_payment_id'):
                val['trans_label'] = move_id.journal_id.code
            elif move_id.move_type in ['out_refund', 'in_refund']:
                val['trans_label'] = 'Credit Note'

        return reconciled_vals

    def write(self, vals):
        from_payment_receipt = self._context.get("from_payment_receipt")
        if not from_payment_receipt and any(self.mapped('is_payment_receipt')) and vals.get('line_ids', False):
            raise UserError("Journal Items of a Payment Receipt should be updated from the payment form.")
        return super().write(vals)
