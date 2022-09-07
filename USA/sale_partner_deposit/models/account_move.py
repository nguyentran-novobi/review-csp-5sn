from odoo import api, fields, models, _


class AccountMoveDeposit(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """
        Override
        Reconcile customer deposits with invoice automatically
        """
        res = super(AccountMoveDeposit, self).action_post()

        for invoice in self.filtered(lambda r: r.move_type == 'out_invoice'):
            deposits = invoice.invoice_line_ids.mapped('sale_line_ids.order_id.deposit_ids')
            self._reconcile_deposit(deposits, invoice)

        return res
