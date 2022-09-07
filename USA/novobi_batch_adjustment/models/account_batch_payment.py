from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    fund_line_ids = fields.One2many('account.batch.deposit.fund.line', 'batch_deposit_id', string='Adjustment Lines')

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('date', 'currency_id', 'payment_ids.amount', 'fund_line_ids.line_amount')
    def _compute_amount(self):
        """
        Call super to calculate the total of all payment lines.
        Then add the total of fund lines.
        """
        super()._compute_amount()

        for batch in self:
            currency = batch.currency_id or batch.journal_id.currency_id or self.env.company.currency_id
            date = batch.date or fields.Date.context_today(self)
            amount = 0
            for fund_line in batch.fund_line_ids:
                liquidity_lines, counterpart_lines, writeoff_lines = fund_line._seek_for_lines()
                for line in liquidity_lines:
                    if line.currency_id == currency:
                        amount += line.amount_currency
                    else:
                        amount += line.company_currency_id._convert(line.balance, currency, line.company_id, date)

            batch.amount += amount

    @api.depends('payment_ids.move_id.is_move_sent', 'payment_ids.is_matched', 'fund_line_ids.move_state')
    def _compute_state(self):
        super()._compute_state()

        for batch in self:
            if not batch.payment_ids and not batch.fund_line_ids:
                batch.state = 'draft'
            elif batch.payment_ids and all(pay.is_matched and pay.is_move_sent for pay in batch.payment_ids):
                batch.state = 'reconciled'
            elif all(pay.is_move_sent for pay in batch.payment_ids) \
                and (not batch.fund_line_ids 
                    or (batch.fund_line_ids and all(line.move_state == 'posted' for line in batch.fund_line_ids))):
                batch.state = 'sent'
            else:
                batch.state = 'draft'

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def validate_adjust_moves(self):
        # Validate all Journal Entries of adjustment lines.
        self.ensure_one()
        self.fund_line_ids.mapped('account_move_id').filtered(lambda r: r.state == 'draft').action_post()

    def validate_batch_button(self):
        res = super().validate_batch_button()
        self.validate_adjust_moves()
        return res

    def action_open_journal_entries(self):
        # Open all Journal Entries from adjustment lines of this batch payment.
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.fund_line_ids.mapped('account_move_id').ids)],
        }


class AccountBatchPaymentLine(models.Model):
    _name = 'account.batch.deposit.fund.line'
    _inherits = {'account.move': 'account_move_id'}
    _check_company_auto = True
    _description = 'Batch Payment Fund Line'

    # == Business fields ==
    account_move_id = fields.Many2one('account.move', string='Journal Entry', ondelete='cascade', check_company=True, required=True)
    outstanding_account_ids = fields.Many2many('account.account', compute='_compute_available_accounts')
    batch_deposit_id = fields.Many2one('account.batch.payment', ondelete='cascade')
    batch_type = fields.Selection(related='batch_deposit_id.batch_type', string='Batch Payment Type')
    move_state = fields.Selection(related='account_move_id.state', string='Journal Entry State')

    # == Synchronized fields with the account.move.lines ==
    line_partner_id = fields.Many2one('res.partner', 'Customer/Vendor')
    line_account_id = fields.Many2one('account.account', 'Account')
    line_communication = fields.Char('Description')
    line_payment_date = fields.Date('Date')
    line_currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='batch_deposit_id.currency_id', store=True)
    line_amount = fields.Monetary('Amount', currency_field='line_currency_id')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_liquid_account_id(self, journal_id, batch_type):
        """
        Get outstanding account from payment method of Journal or Accounting setting
        If journal have multiple payment methods having outstanding account => choose account from method
        with lowest sequence
        """
        batch_payment_method = self.batch_deposit_id.payment_method_id

        if batch_type == 'inbound':
            payment_method_lines = journal_id.inbound_payment_method_line_ids
            liquid_account = journal_id.company_id.account_journal_payment_debit_account_id
        else:
            payment_method_lines = journal_id.outbound_payment_method_line_ids
            liquid_account = journal_id.company_id.account_journal_payment_credit_account_id

        payment_method_lines = payment_method_lines\
            .filtered(lambda r: r.payment_method_id == batch_payment_method and r.payment_account_id)\
            .sorted(lambda r: r.sequence)

        if payment_method_lines:
            return payment_method_lines[0].payment_account_id
        else:
            return liquid_account

    @api.model
    def _prepare_liquidity_move_line_vals(self):
        self.ensure_one()
        ref = self.line_communication or self.batch_deposit_id.display_name + ' Adjustment'
        amount = company_currency_amount = self.line_amount
        to_debit = bool(
            self.batch_type == 'inbound' and amount >= 0 or self.batch_type == 'outbound' and amount <= 0)
        liquid_account_id = self._get_liquid_account_id(self.journal_id, self.batch_type)

        if self.company_id and self.line_currency_id != self.company_id.currency_id:
            # Convert amount from adjust line currency to company currency
            company_currency_amount = self.line_currency_id._convert(
                amount,
                self.company_id.currency_id,
                self.company_id,
                self.line_payment_date,
            )

        return {
            'name': ref,
            'move_id': self.account_move_id.id,
            'partner_id': self.line_partner_id.id,
            'date': self.line_payment_date,
            'currency_id': self.line_currency_id.id,
            'account_id': liquid_account_id.id,
            'debit': to_debit and abs(company_currency_amount) or 0.0,
            'credit': not to_debit and abs(company_currency_amount) or 0.0,
            'amount_currency': to_debit and abs(amount) or -abs(amount)
        }

    @api.model
    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        self.ensure_one()

        if not counterpart_account_id:
            counterpart_account_id = self.line_account_id.id

        liquidity_line_vals = self._prepare_liquidity_move_line_vals()
        counterpart_line_vals = liquidity_line_vals.copy()
        counterpart_line_vals.update({
            'account_id': counterpart_account_id,
            'debit': liquidity_line_vals['credit'],
            'credit': liquidity_line_vals['debit'],
            'amount_currency': -liquidity_line_vals['amount_currency']
        })

        return liquidity_line_vals, counterpart_line_vals

    def _seek_for_lines(self):
        """ Helper used to dispatch the journal items between:
        - The lines using the liquidity account.
        - The lines using the transfer account.
        - The lines being not in one of the two previous categories.
        :return: (liquidity_lines, suspense_lines, other_lines)
        """
        liquidity_lines = self.env['account.move.line']
        counterpart_lines = self.env['account.move.line']
        other_lines = self.env['account.move.line']
        counterpart_account = self.line_account_id

        for line in self.account_move_id.line_ids:
            if line.account_id in self._get_valid_liquidity_accounts():
                liquidity_lines += line
            elif line.account_id == counterpart_account:
                counterpart_lines += line
            else:
                other_lines += line
        return liquidity_lines, counterpart_lines, other_lines

    def _get_init_sync_values(self, line_ids=False):
        self.ensure_one()
        vals = {
            'batch_fund_line_id': self.id,
            'partner_id': self.line_partner_id.id,
            'currency_id': self.line_currency_id.id,
            'date': self.line_payment_date
        }
        if line_ids:
            vals['line_ids'] = line_ids
        return vals

    def _get_valid_liquidity_accounts(self):
        """
        Get all liquidity accounts from payment methods of journal and setting
        :return:
        """
        journal = self.batch_deposit_id.journal_id
        setting_liquid_accounts = journal.company_id.account_journal_payment_debit_account_id \
                                     + journal.company_id.account_journal_payment_credit_account_id
        journal_liquid_accounts = (journal.inbound_payment_method_line_ids + journal.outbound_payment_method_line_ids)\
            .mapped('payment_account_id')
        return setting_liquid_accounts + journal_liquid_accounts

    def get_aml_adjustments(self, liquid_accounts=None):
        """
        Get account.move.line record posted by Adjustments, which is used in Reviewed screen and Reconciliation screen
        Only get lines that have not been reviewed or reconciled
        :param liquid_accounts:
        """
        self.ensure_one()

        liquid_accounts = liquid_accounts or self._get_valid_liquidity_accounts()
        sign = 1 if self.batch_deposit_id.batch_type == 'inbound' else -1
        company_currency = self.company_id.currency_id
        if self.account_move_id.state == 'posted':
            if self.line_currency_id != company_currency:
                # Convert amount from adjust line currency to company currency
                line_amount = self.line_currency_id._convert(
                    self.line_amount,
                    company_currency,
                    self.company_id,
                    self.line_payment_date,
                )
            else:
                line_amount = self.line_amount
            return self.account_move_id.line_ids.filtered(lambda r: r.account_id in liquid_accounts and
                                                          (company_currency.compare_amounts(sign * line_amount, r.debit) == 0
                                                           or company_currency.compare_amounts(-sign * line_amount, r.credit) == 0) and
                                                          not r.reconciled)
        else:
            return self.env['account.move.line']

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # Add Bank Journal to newly created entries
        for vals in vals_list:
            batch_id = self.env['account.batch.payment'].browse(vals['batch_deposit_id'])

            journal = batch_id.journal_id
            vals.update({
                'move_type': 'entry',
                'journal_id': journal.id,
                'currency_id': (journal.currency_id or journal.company_id.currency_id).id,
            })
            if 'date' not in vals and 'line_payment_date' in vals:
                vals['date'] = vals['line_payment_date']

        res = super().create(vals_list)

        for index, line_id in enumerate(res):
            counterpart_account_id = vals_list[index].get('line_account_id', False)
            to_write = line_id._get_init_sync_values()
            move_line_vals = line_id._prepare_move_line_default_vals(counterpart_account_id=counterpart_account_id)
            if 'line_ids' not in vals_list[index]:
                to_write['line_ids'] = [Command.create(line_vals) for line_vals in move_line_vals]

            line_id.account_move_id.write(to_write)

        return res

    def write(self, vals):
        if any(record.move_state != 'draft' for record in self):
            raise ValidationError(_('Cannot edit adjustment lines having posted journal entries.'))
        res = super().write(vals)
        self.with_context(sync_to_move_from_batch_form=True)._synchronize_to_moves(set(vals.keys()))
        return res

    # -------------------------------------------------------------------------
    # SYNCHRONIZATION account.batch.payment.fund.line <-> account.move
    # -------------------------------------------------------------------------

    def _synchronize_to_moves(self, changed_fields):
        """
        Update the account.move regarding the modified account.batch.deposit.fund.line
        :param changed_fields: A list containing all modified fields on account.batch.deposit.fund.line
        :return:
        """
        if self._context.get('skip_account_move_synchronization'):
            return

        # Cannot sync Journal
        if not any(field_name in changed_fields for field_name in (
            'line_communication', 'line_amount', 'line_currency_id', 'line_partner_id',
            'batch_type', 'line_payment_date', 'line_account_id'
        )):
            return

        for line_id in self.with_context(skip_account_move_synchronization=True):
            liquidity_lines, counterpart_lines, other_lines = line_id._seek_for_lines()

            line_vals_list = self._prepare_move_line_default_vals()
            line_ids_commands = [Command.update(liquidity_lines.id, line_vals_list[0])]

            if counterpart_lines:
                line_ids_commands.append(Command.update(counterpart_lines.id, line_vals_list[1]))
            else:
                line_ids_commands.append(Command.create(line_vals_list[1]))

            for line in other_lines:
                line_ids_commands.append(Command.delete(line.id))

            line_id.account_move_id.write(line_id._get_init_sync_values(line_ids=line_ids_commands))

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def action_open_journal_entry(self):
        self.ensure_one()
        return {
            'name': _('Journal Entry'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'type': 'ir.actions.act_window',
        }

    @api.depends('batch_deposit_id', 'batch_deposit_id.journal_id')
    def _compute_available_accounts(self):
        for record in self:
            record.outstanding_account_ids = record._get_valid_liquidity_accounts()
