from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """
        Override
        Reconcile vendor deposits with bill automatically
        """
        res = super(AccountMove, self).action_post()
        for invoice in self.filtered(lambda r: r.move_type == 'in_invoice'):
            deposits = invoice.invoice_line_ids.mapped('purchase_line_id.order_id.deposit_ids')
            self._reconcile_deposit(deposits, invoice)

        return res
