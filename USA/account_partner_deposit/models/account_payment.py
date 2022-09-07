from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    property_account_customer_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                           string='Customer Deposit Account',
                                                           domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
                                                                                ('deprecated', '=', False), ('reconcile', '=', True)])
    property_account_vendor_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                         string='Vendor Deposit Account',
                                                         domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_prepayments').id]),
                                                                              ('deprecated', '=', False), ('reconcile', '=', True)])
    deposit_ids = fields.Many2many('account.move', string='Deposit Entries',
                                   help='Journal entries are created when reconciling invoices and deposits')
    is_deposit = fields.Boolean('Is a Deposit?')
    related_commercial_partner_id = fields.Many2one(related='partner_id.commercial_partner_id',
                                                    string='Related Commercial Partner')

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('partner_id')
    def _update_default_deposit_account(self):
        """
        Populate deposit account from contact
        """
        if self.partner_id and self.is_deposit:
            if self.partner_id.property_account_customer_deposit_id and self.partner_type == 'customer':
                self.property_account_customer_deposit_id = self.partner_id.property_account_customer_deposit_id.id
            elif self.partner_id.property_account_vendor_deposit_id and self.partner_type == 'supplier':
                self.property_account_vendor_deposit_id = self.partner_id.property_account_vendor_deposit_id.id

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override to add deposit move line like a write-off move line to JE of deposit payment
        """
        for values in vals_list:
            if values.get('is_deposit'):
                account_id = values.get('property_account_customer_deposit_id') \
                             or values.get('property_account_vendor_deposit_id')
                if not account_id:
                    raise ValidationError(_('Deposit account has not been set'))
                if values.get('currency_id'):
                    currency = self.env['res.currency'].browse(values['currency_id'])
                elif values.get('company_id') and values['company_id'] != self.env.company.id:
                    company = self.env['res.company'].browse(values['company_id'])
                    currency = company.currency_id
                else:
                    currency = self.env.company.currency_id
                values['write_off_line_vals'] = {
                    'account_id': account_id,
                    'amount': -currency.round(values.get('amount', 0.0))
                }

        return super(PaymentDeposit, self).create(vals_list)

    def _synchronize_to_moves(self, changed_fields):
        """
        Override to update move lines of deposit payment JE when changing fields on the deposit payment form
        """
        if self._context.get('skip_account_move_synchronization'):
            return

        deposit_payments = self.with_context(skip_account_move_synchronization=True).filtered(lambda x: x.is_deposit)
        if any(field in changed_fields for field in ['partner_id', 'partner_bank_id', 'date', 'payment_reference',
                                                     'amount', 'currency_id', 'property_account_customer_deposit_id',
                                                     'property_account_vendor_deposit_id']):
            for payment in deposit_payments:
                liquidity_lines, counterpart_lines, other_lines = payment._seek_for_lines()
                deposit_account = payment.property_account_customer_deposit_id or payment.property_account_vendor_deposit_id
                other_line_vals = {
                    'amount': -payment.amount,
                    'account_id': deposit_account.id
                }
                line_vals_list = payment._prepare_move_line_default_vals(write_off_line_vals=other_line_vals)
                # Update write-off move line of JE of deposit

                if other_lines:
                    if len(line_vals_list) == 3:
                        # If JE has write-off move line, update this line
                        other_line_command = [Command.update(other_lines[0].id, line_vals_list[2])]
                    else:
                        # When payment amount is 0, delete write-off move line
                        other_line_command = [Command.delete(other_lines[0].id)]
                elif not other_lines and not payment.currency_id.is_zero(payment.amount):
                    # Create write-off move line when payment amount is not 0
                    other_line_command = [Command.create(line_vals_list[2])]
                else:
                    other_line_command = []

                line_ids_commands = [
                    Command.update(liquidity_lines.id, line_vals_list[0]),
                    Command.update(counterpart_lines.id, line_vals_list[1]),
                ]
                line_ids_commands += other_line_command
                payment.move_id.write({
                    'partner_id': payment.partner_id.id,
                    'currency_id': payment.currency_id.id,
                    'partner_bank_id': payment.partner_bank_id.id,
                    'line_ids': line_ids_commands
                })
            super(PaymentDeposit, self - deposit_payments)._synchronize_to_moves(changed_fields)
        else:
            super(PaymentDeposit, self)._synchronize_to_moves(changed_fields)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _validate_order_commercial_partner(self, order_field, model_name):
        """
        Helper method: Check if commercial partner of deposit is the same as the one of payment
        """
        for payment in self:
            commercial_partner = payment.partner_id.commercial_partner_id
            partner_type = order_field == 'sale_deposit_id' and 'customer' or 'vendor'
            if payment[order_field] and payment[order_field].partner_id.commercial_partner_id != commercial_partner:
                raise ValidationError(_('The {} of {} does not match with the one of deposit'.
                                        format(partner_type, model_name)))
