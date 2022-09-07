from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    sale_deposit_id = fields.Many2one('sale.order', 'Sales Order',
                                      domain="[('partner_id.commercial_partner_id', '=', related_commercial_partner_id), ('state', 'in', ['sale', 'done'])]",
                                      help='Is this deposit made for a particular Sale Order?')

    @api.onchange('partner_id')
    def _onchange_sale_deposit_partner_id(self):
        commercial_partner = self.partner_id.commercial_partner_id
        if self.sale_deposit_id and self.sale_deposit_id.partner_id.commercial_partner_id != commercial_partner:
            self.sale_deposit_id = False

    def action_post(self):
        """Override"""
        # Check the customer of deposit and order for the last time before validating
        self._validate_order_commercial_partner('sale_deposit_id', 'Sales Order')

        # Check if total deposit amount of an order has exceeded amount of this order
        for record in self:
            order = record.sale_deposit_id
            if order:
                deposit_total = order.company_id.currency_id._convert(
                    record.amount_total_signed,
                    order.currency_id,
                    order.company_id,
                    record.date or fields.Date.today()
                )
                if order.currency_id.compare_amounts(deposit_total, order.remaining_total) > 0:
                    raise ValidationError(_('Total deposit amount cannot exceed sales order amount'))

        return super(PaymentDeposit, self).action_post()
