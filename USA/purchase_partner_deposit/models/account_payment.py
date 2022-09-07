from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    purchase_deposit_id = fields.Many2one('purchase.order', 'Purchase Order',
                                          domain="[('partner_id.commercial_partner_id', '=', related_commercial_partner_id), ('state', 'in', ['purchase', 'done'])]",
                                          help='Is this deposit made for a particular Purchase Order?')

    @api.onchange('partner_id')
    def _onchange_purchase_deposit_partner_id(self):
        commercial_partner = self.partner_id.commercial_partner_id
        if self.purchase_deposit_id and self.purchase_deposit_id.partner_id.commercial_partner_id != commercial_partner:
            self.purchase_deposit_id = False

    def action_post(self):
        """Override"""
        # Check the vendor of deposit and order for the last time before validating
        self._validate_order_commercial_partner('purchase_deposit_id', 'Purchase Order')

        # Check if total deposit amount of an order has exceeded amount of this order
        for record in self:
            order = record.purchase_deposit_id
            if order:
                deposit_total = order.company_id.currency_id._convert(
                    record.amount_total_signed,
                    order.currency_id,
                    order.company_id,
                    record.date or fields.Date.today()
                )
                if order.currency_id.compare_amounts(deposit_total, order.remaining_total) > 0:
                    raise ValidationError(_('Total deposit amount cannot exceed purchase order amount'))

        return super(PaymentDeposit, self).action_post()
