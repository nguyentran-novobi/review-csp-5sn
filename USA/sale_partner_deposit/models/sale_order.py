from odoo import api, fields, models, _


class DepositSalesOrder(models.Model):
    _inherit = 'sale.order'

    deposit_ids = fields.One2many('account.payment', 'sale_deposit_id', string='Deposits',
                                  domain=[('state', 'not in', ['draft', 'cancel'])])
    deposit_count = fields.Integer('Deposit Count', compute='_compute_deposit_amount')
    deposit_total = fields.Monetary(string='Total Deposit', compute='_compute_deposit_amount')
    remaining_total = fields.Monetary(string='Net Total', compute='_compute_deposit_amount')

    @api.depends('amount_total', 'deposit_ids', 'deposit_ids.state')
    def _compute_deposit_amount(self):
        for order in self:
            deposit_total = sum(order.company_id.currency_id._convert(
                deposit.amount_total_signed,
                order.currency_id,
                order.company_id,
                deposit.date or fields.Date.today()
            ) for deposit in order.deposit_ids)

            order.update({
                'deposit_total': deposit_total,
                'deposit_count': len(order.deposit_ids),
                'remaining_total': order.amount_total - deposit_total,
            })

    def action_view_deposit(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('account_partner_deposit.action_account_payment_customer_deposit')
        if len(self.deposit_ids) > 1:
            action['domain'] = [('id', 'in', self.deposit_ids.ids)]
        elif self.deposit_ids:
            form_view = [(self.env.ref('account_partner_deposit.view_account_payment_deposit_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = self.deposit_ids.id

        return action

    def action_make_a_deposit(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('account_partner_deposit.order_make_deposit_action')
        action['context'] = dict(default_currency_id=self.currency_id.id)

        return action
