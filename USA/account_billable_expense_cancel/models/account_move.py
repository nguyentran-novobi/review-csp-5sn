from odoo import models, fields, Command

class USAAccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        """
        Remove the billable expense line from Invoice if users check 'remove_expenses' on wizard.
        """
        super(USAAccountMove, self).button_draft()
        if self._context.get('remove_expenses', False):
            for record in self:
                record.invoice_line_ids = [Command.delete(line_id.id) for line_id in record.invoice_line_ids if line_id.is_billable]