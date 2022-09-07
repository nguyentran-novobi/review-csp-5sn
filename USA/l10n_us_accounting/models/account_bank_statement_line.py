from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from ..utils.bank_statement_line_utils import extract_check_number, is_check_statement
import logging

_logger = logging.getLogger(__name__)

class BankStatementLine(models.Model):
    _name = 'account.bank.statement.line'
    _inherit = ['account.bank.statement.line', 'mail.thread', 'mail.activity.mixin']

    # Reconciliation Fields
    status = fields.Selection(
        [('open', 'Open'), ('confirm', 'Reviewed'), ('reconciled', 'Reconciled'), ('excluded', 'Excluded')],
        string='Reconciliation Status', required=True, copy=False, default='open', tracking=True)
    matched_journal_entry_ids = fields.Many2many('account.move', string='Matched Journal Entries', compute='_compute_matched_journal_entries')
    # Technical fields
    check_number_cal = fields.Char('Check Number from Statement\'s name', compute='_compute_check_number_cal', store=True,
                                   help='Check number which is calculated from name of bank statement line, used to map with check number from account payment')

    @api.depends('payment_ref')
    def _compute_check_number_cal(self):
        for record in self:
            payment_ref = record.payment_ref
            record.check_number_cal = is_check_statement(payment_ref) and extract_check_number(payment_ref) or False

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def get_reconciliation_lines(self):
        """
        Helper function to return aml that needs to be reconciled:
        + for Outstanding Payment/Receipt accounts, return matched payment line
        + for writeoff/AR/AP accounts, return itself

        Used in:
        + review a BSL (process_bank_statement_line)
        + undo review (button_undo_reconciliation)

        start a reconciliation session (_get_aml)
        :return: aml that needs to be reconciled
        """
        if not self:
            return self.env['account.move.line']

        journal = self[0].journal_id
        exclude_accounts = [journal.default_account_id, journal.suspense_account_id]
        outstanding_accounts = journal.get_all_journals_outstanding_accounts()

        result_lines = self.env['account.move.line']

        for line in self.mapped('move_id.line_ids'):
            if line.account_id in exclude_accounts:
                continue
            if line.account_id in outstanding_accounts:
                result_lines += line.reconciled_line_id
            else:
                result_lines += line

        return result_lines

    def get_reconciled_states(self):
        """
        Return list of BSL's items' bank_reconciled state
        + Write off lines: itself
        + Outstanding line: linked payment's state

        Called in finish a reconciliation session (mark_bank_reconciled)
        """
        reconciliation_lines = self.get_reconciliation_lines()

        return reconciliation_lines.mapped('bank_reconciled')

    @api.model
    def update_historical_reconciliation_data(self):
        _logger.info('===== Starting update historical bank statement data =====')
        query = """
            UPDATE account_bank_statement_line SET status = 'confirm'
            WHERE is_reconciled = TRUE and status = 'open';
        """
        self._cr.execute(query)

        _logger.info('===== Ending update historical bank statement data =====')

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def action_exclude(self, exclude_ids=None):
        """
        To exclude bank statement lines, could be called directly or by using _rpc in reconciliation_model.js
        :param exclude_ids: list of bank statement lines id from args of _rpc
        """
        if exclude_ids:
            self = self.browse(exclude_ids)
        rec_ids = self.filtered(lambda r: r.status not in ['open', 'excluded'])
        if rec_ids:
            raise UserError(_('You cannot exclude any bank statement line which has been reviewed or reconciled.'))
        self.write({'status': 'excluded'})

    def button_action_review(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'bank_statement_reconciliation_view',
            'context': {'statement_line_ids': self.ids, 'company_ids': self.mapped('company_id').ids},
        }

    def button_undo_review(self):
        """
        To undo Review status of a BSL. Called in BSL Tree or BS form.
        """
        rec_ids = self.filtered(lambda r: r.status != 'confirm')
        if rec_ids:
            raise UserError(_('You cannot undo review any bank statement line which has not been reviewed.'))
        self.with_context(force_unlink=1).button_undo_reconciliation()

    def button_undo_exclude(self):
        """
        To undo Exclude status of a BSL. Called in BSL Tree or BS form.
        """
        rec_ids = self.filtered(lambda r: r.status != 'excluded')
        if rec_ids:
            raise UserError(_('You cannot undo exclude any bank statement line which has not been excluded.'))
        self.write({'status': 'open'})

    def button_undo_reconciliation(self):
        # Override Odoo's, used to undo review bank statement lines.
        # Need to set status of bank statement lines back to 'open' + aml's temporary reconciled to False
        reconciliation_lines = self.get_reconciliation_lines()
        if True in reconciliation_lines.mapped('bank_reconciled'):
            raise ValidationError(_('You cannot undo review any bank statement line that was reconciled partially'))
        reconciliation_lines.write({'temporary_reconciled': False})
        super().button_undo_reconciliation()
        self.write({'status': 'open'})

    @api.depends('move_id.line_ids', 'move_id.line_ids.reconciled_line_id')
    def _compute_matched_journal_entries(self):
        """
        Get all JEs (of Payments/Adjustment lines) are matched with this statement line
        """
        for record in self:
            record.matched_journal_entry_ids = record.mapped('move_id.line_ids') \
                .filtered(lambda l: l.account_id in record.journal_id.get_all_journals_outstanding_accounts()) \
                .mapped('reconciled_line_id.move_id')

    def action_open_matched_journal_entries(self):
        # Open all Journal Entries (of Payments/Adjustment lines) are matched with this statement line
        self.ensure_one()

        return {
            'name': _('Matched Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.matched_journal_entry_ids.ids)],
        }
