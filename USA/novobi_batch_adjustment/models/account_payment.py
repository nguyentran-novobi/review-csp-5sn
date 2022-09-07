from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('state')
    def _compute_batch_payment_id(self):
        """
        Override
        New update in v15 of Odoo: when setting payment to draft, Odoo remove many2one link to batch payment.
        However, _compute_amount() of batch payment isn't called. We'll call _compute_amount() ourselves
        """
        for payment in self:
            batch_payment = payment.batch_payment_id
            payment.batch_payment_id = payment.state == 'posted' and payment.batch_payment_id or None
            if batch_payment and not payment.batch_payment_id:
                batch_payment._compute_amount()
