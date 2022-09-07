from odoo import fields, models, api


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    # -------------------------------------------------------------------------
    # BATCH PAYMENT
    # -------------------------------------------------------------------------

    @api.model
    def get_move_lines_by_batch_payment(self, st_line_id, batch_payment_id):
        """
        Override
        Also get move lines for adjustments of batch payment.
        """
        res = super(AccountReconciliation, self).get_move_lines_by_batch_payment(st_line_id, batch_payment_id)
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)
        batch = self.env['account.batch.payment'].browse(batch_payment_id)
        move_lines = self.env['account.move.line']
        for line in batch.fund_line_ids:
            move_lines |= line.get_aml_adjustments()
        aml_list = [self._prepare_js_reconciliation_widget_move_line(st_line, line) for line in move_lines]

        return res + aml_list
