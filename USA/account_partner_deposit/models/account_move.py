import json
from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError


class AccountMoveDeposit(models.Model):
    _inherit = 'account.move'

    is_deposit = fields.Boolean('Is a Deposit?')

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    def _compute_payments_widget_to_reconcile_info(self):
        """
        Override to add deposit to Outstanding credits/debits widget on invoice/bill form
        """
        super(AccountMoveDeposit, self)._compute_payments_widget_to_reconcile_info()

        for move in self:
            payments_widget_vals = json.loads(move.invoice_outstanding_credits_debits_widget)
            if not payments_widget_vals:
                payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.state != 'posted' or move.payment_state not in ('not_paid', 'partial')  \
                    or move.move_type not in ['out_invoice', 'in_invoice']:
                continue

            payment_type = move.move_type == 'out_invoice' and 'inbound' or 'outbound'
            domain = [('account_id.reconcile', '=', True),
                      ('payment_id.is_deposit', '=', True),
                      ('payment_id.payment_type', '=', payment_type),
                      ('move_id.state', '=', 'posted'),
                      ('partner_id', '=', move.commercial_partner_id.id),
                      ('reconciled', '=', False),
                      '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0)]

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')


            for line in self.env['account.move.line'].search(domain):
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                else:
                    # Different foreign currencies.
                    amount = move.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency': move.currency_id.symbol,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'position': move.currency_id.position,
                    'payment_id': line.payment_id.id,
                    'digits': [69, move.currency_id.decimal_places],
                    'payment_date': fields.Date.to_string(line.date),
                })

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = json.dumps(payments_widget_vals)
            move.invoice_has_outstanding = True

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def button_draft(self):
        """
        Override
        """
        # When setting invoice/bill to draft, delete all intermediate JEs so next time deposits will be shown in
        # Outstanding credits/debits widget
        non_entries = self.filtered(lambda x: x.move_type != 'entry')
        lines = non_entries.mapped('line_ids')
        if lines:
            sql = """
                SELECT am.id
                    FROM account_partial_reconcile as apr
                    JOIN account_move_line as aml ON (apr.debit_move_id = aml.id OR apr.credit_move_id = aml.id) AND 
                                                     (apr.debit_move_id IN %(line_ids)s OR apr.credit_move_id IN %(line_ids)s)
                    JOIN account_move as am ON am.id = aml.move_id
                WHERE am.is_deposit = TRUE AND am.state = 'posted';
            """
            self.env.cr.execute(sql, {'line_ids': tuple(lines.ids)})
            intermediate_moves = [res[0] for res in self.env.cr.fetchall()]
            intermediate_moves = self.env['account.move'].browse(intermediate_moves)

            # Set intermediate JEs to draft and then delete them
            if intermediate_moves:
                intermediate_moves.button_draft()
                intermediate_moves.with_context(force_delete=True).unlink()

        # When setting deposit or its JE to draft, delete intermediate JEs
        deposit_entries = (self - non_entries).filtered(lambda x: x.is_deposit and x.payment_id)
        intermediate_moves = deposit_entries.mapped('payment_id.deposit_ids')
        if intermediate_moves:
            intermediate_moves.filtered(lambda move: move.state == 'posted').button_draft()
            intermediate_moves.with_context(force_delete=True).unlink()

        super(AccountMoveDeposit, self).button_draft()

    def js_assign_outstanding_line(self, credit_aml_id):
        """
        Override to reconcile invoice/bill and deposit
        :param credit_aml_id: move line of deposit contains deposit account
        We will create new intermediate JE containing AR/AP account and deposit account move lines
        Reconcile deposit account lines of deposit and this new JE
        Reconcile AR/AP account lines of invoice/bill and this new JE
        """
        self.ensure_one()
        credit_aml = self.env['account.move.line'].browse(credit_aml_id)
        if credit_aml.payment_id and credit_aml.payment_id.is_deposit:
            line_to_reconcile = self.line_ids.filtered(lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))
            register_payment_line = self._create_deposit_to_payment_journal_entry(credit_aml, line_to_reconcile)
            if register_payment_line and line_to_reconcile:
                (register_payment_line + line_to_reconcile).reconcile()
        else:
            return super(AccountMoveDeposit, self).js_assign_outstanding_line(credit_aml_id)

    def js_remove_outstanding_partial(self, partial_id):
        """
        Override to remove intermediate JE when un-reconciling deposit and invoice/bill
        """
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        intermediate_move = self.env['account.move'].browse()
        if partial.credit_move_id.move_id.is_deposit:
            intermediate_move = partial.credit_move_id.move_id
        elif partial.debit_move_id.move_id.is_deposit:
            intermediate_move = partial.debit_move_id.move_id

        res = super(AccountMoveDeposit, self).js_remove_outstanding_partial(partial_id)

        if intermediate_move:
            intermediate_move.button_draft()
            intermediate_move.with_context(force_delete=True).unlink()

        return res

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _create_deposit_to_payment_journal_entry(self, payment_line, invoice_line):
        """
        Create intermediate JE to reconcile deposit and invoice/bill
        JE used to apply to invoice:
            Dr: Customer deposit account
            Cr: AR account
        JE used to apply to bill:
            Dr: AP account
            Cr: Prepayment account
        :return: Payable/receivable move lines of new entry
        """
        total_invoice_amount = abs(sum(invoice_line.mapped('amount_residual')))
        amount = min(total_invoice_amount, abs(payment_line.amount_residual))
        foreign_currency_amount = company_currency_amount = 0.0
        partial_amount = 0.0
        new_move_currency = invoice_line.company_currency_id

        if self.currency_id.is_zero(amount):
            return self.env['account.move.line']

        if self.env.context.get('partial_amount', False):
            partial_amount = self.env.context.get('partial_amount')

        if payment_line.currency_id == invoice_line.currency_id \
                and payment_line.currency_id != payment_line.company_id.currency_id:
            # Invoice and deposit have the same currency but different with company currency
            total_invoice_amount_currency = abs(sum(invoice_line.mapped('amount_residual_currency')))
            foreign_currency_amount= min(total_invoice_amount_currency, abs(payment_line.amount_residual_currency))
            if not self.currency_id.is_zero(partial_amount):
                # When apply partially, convert partial amount to company currency
                foreign_currency_amount = partial_amount
            # Convert amount from invoice/deposit currency to company currency, this will be amount of debit/credit of new JE
            company_currency_amount = payment_line.currency_id._convert(foreign_currency_amount, payment_line.company_id.currency_id,
                                                                        payment_line.company_id, payment_line.date)
            # Currency of new JE will be same as invoice/deposit instead of company currency
            new_move_currency = payment_line.payment_id.currency_id
        else:
            # For remaining cases, new JE will have company currency
            if not self.currency_id.is_zero(partial_amount):
                amount = partial_amount

        # Get deposit journal
        company = payment_line.company_id
        if payment_line.debit > 0:
            journal = company.vendor_deposit_journal_id
        elif payment_line.credit > 0:
            journal = company.customer_deposit_journal_id
        else:
            journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)

        # Create new account.move
        debit_account, credit_account = self._get_account_side(payment_line, invoice_line)
        reference = 'Deposit to Payment'
        payment = payment_line.payment_id
        date = self.invoice_date or fields.Date.today()

        new_account_move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': date,
            'ref': reference,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'is_deposit': True,
            'move_type': 'entry',
            'currency_id': new_move_currency.id,
            'line_ids': [
                Command.create({
                    'partner_id': payment_line.partner_id.id,
                    'account_id': debit_account.id,
                    'debit': company_currency_amount or amount,
                    'credit': 0,
                    'date': date,
                    'name': reference,
                    'currency_id': new_move_currency.id,
                    'amount_currency': foreign_currency_amount or amount
                }),
                Command.create({
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'account_id': credit_account.id,
                    'debit': 0,
                    'credit': company_currency_amount or amount,
                    'date': date,
                    'name': reference,
                    'currency_id': new_move_currency.id,
                    'amount_currency': -foreign_currency_amount or -amount
                })
            ],
        })
        new_account_move.action_post()

        # Reconcile new move and deposit move
        (payment_line + new_account_move.line_ids.filtered(lambda l: l.account_id == payment_line.account_id)).reconcile()
        payment.write({'deposit_ids': [Command.link(new_account_move.id)]})

        return new_account_move.line_ids.filtered(lambda l: l.account_id.internal_type in ('payable', 'receivable'))

    def _get_account_side(self, payment_line, invoice_line):
        debit_account = payment_line.credit > 0 and payment_line.account_id or invoice_line.account_id
        credit_account = payment_line.debit > 0 and payment_line.account_id or invoice_line.account_id

        return debit_account, credit_account

    def _reconcile_deposit(self, deposits, invoice):
        """
        Helper method: reconcile deposit with invoice/bill automatically when confirming invoice/bill
        """
        for deposit in deposits.filtered(lambda r: r.state == 'posted'):
            if deposit.partner_id.commercial_partner_id != invoice.partner_id.commercial_partner_id:
                raise ValidationError(_('Customer/Vendor of invoice/bill is different from the one of deposit'))
            move_type = invoice.move_type
            move_lines = deposit.line_ids.filtered(lambda line: line.account_id.reconcile and line.account_id.internal_type != 'liquidity' and not line.reconciled)
            if move_type == 'out_invoice':
                move_line = move_lines.filtered(lambda line: line.credit > 0)
            else:
                move_line = move_lines.filtered(lambda line: line.debit > 0)
            if move_line:
                invoice.js_assign_outstanding_line(move_line.id)

    def _get_reconciled_info_JSON_values(self):
        """
        Override
        Add label of applied transactions to dict values to show in payment widget on invoice form
        """
        reconciled_vals = super(AccountMoveDeposit, self)._get_reconciled_info_JSON_values()

        for val in reconciled_vals:
            move = self.browse(val.get('move_id'))
            if move.is_deposit:
                val['trans_label'] = 'Deposit'

        return reconciled_vals
