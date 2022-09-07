from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    batch_fund_line_id = fields.Many2one('account.batch.deposit.fund.line', string='Batch Payment - Adjustment line')

    def write(self, vals):
        if 'line_ids' in vals and self.mapped('batch_fund_line_id') \
                and not self._context.get('sync_to_move_from_batch_form'):
            raise ValidationError(_('Journal Items of a Batch Adjustment should be updated from the Batch payment form.'))

        return super(AccountMove, self).write(vals)
