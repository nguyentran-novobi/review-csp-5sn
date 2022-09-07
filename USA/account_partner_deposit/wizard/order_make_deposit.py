from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class OrderMakeDeposit(models.TransientModel):
    _name = 'order.make.deposit'
    _description = 'Make Deposit From Sales/Purchase Order'

    deposit_option = fields.Selection([
        ('fixed', 'By fixed amount'),
        ('percentage', 'By percentage')
    ], string='How do you want to make a deposit?', default='fixed')
    amount = fields.Float(string='Deposit amount', digits='Account')
    percentage = fields.Float(string='Deposit amount', digits='Account', related='amount', readonly=False)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    def action_create_deposit(self):
        if self._context.get('active_id', False):
            if self.currency_id.compare_amounts(self.amount, 0) <= 0:
                raise ValidationError(_('Deposit amount must be greater than 0'))

            active_model = self._context.get('active_model', False)
            order = self.env[active_model].browse(self._context.get('active_id'))
            amount = self.deposit_option == 'fixed' and self.amount or (self.amount * order.amount_total) / 100
            view_id = self.env.ref('account_partner_deposit.account_payment_deposit_from_order_form_view').id
            context = {
                'default_is_deposit': True,
                'default_partner_id': order.partner_id.id,
                'default_amount': amount,
                'default_currency_id': order.currency_id.id,
                'default_move_journal_types': ('bank', 'cash')
            }

            if active_model == 'sale.order':
                context.update({
                    'default_payment_type': 'inbound',
                    'default_partner_type': 'customer',
                    'default_sale_deposit_id': order.id
                })
            elif active_model == 'purchase.order':
                context.update({
                    'default_payment_type': 'outbound',
                    'default_partner_type': 'supplier',
                    'default_purchase_deposit_id': order.id
                })

            return {
                'name': 'Make a Deposit',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'target': 'new',
                'view_id': view_id,
                'context': context
            }
