# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from collections import defaultdict


class AccountReconcileModelUSA(models.Model):
    _inherit = 'account.reconcile.model'

    # Override to update title of "invoice_matching"
    rule_type = fields.Selection(selection=[
        ('writeoff_button', 'Manually create a write-off on clicked button.'),
        ('writeoff_suggestion', 'Suggest counterpart values.'),
        ('invoice_matching', 'Match existing transactions.')
    ], string='Type', default='writeoff_suggestion', required=True)

    def _apply_conditions(self, query, params, check=False):
        """
        Override
        Add more conditions to bank rules matching. BSL and transactions must be
        - Same journal
        - Same transaction type (Receive/Send money)
        - Transaction date <= BSL date
        - Same payee (OOTB)
        """
        self.ensure_one()

        if self.rule_type == 'invoice_matching':
            select = """
            AS aml_date_maturity,
            aml.date AS aml_date,
            """

            join_st = """
            ON st_line_move.id = st_line.move_id
            JOIN account_journal journal ON journal.id = st_line_move.journal_id
            """

            join = """ON payment.move_id = move.id
            LEFT JOIN account_payment_method_line payment_method_line ON payment_method_line.id = payment.payment_method_line_id
            LEFT JOIN account_payment_method payment_method ON payment_method.id = payment_method_line.payment_method_id
            """

            where = """
            aml.company_id = st_line_move.company_id
            AND (
                payment.id IS NULL OR
                (
                    aml.journal_id = journal.id AND
                    CASE WHEN st_line.amount < 0 THEN payment_method.payment_type = 'outbound' ELSE payment_method.payment_type = 'inbound' END
                )
            ) -- Match payment type
            AND aml.bank_reconciled IS NOT TRUE                 -- Has not been reconciled
            AND aml.date <= st_line_move.date           
            """

            query = query.replace('AS aml_date_maturity,', select)
            query = query.replace('ON st_line_move.id = st_line.move_id', join_st)
            query = query.replace('ON payment.move_id = move.id', join)
            query = query.replace('aml.company_id = st_line_move.company_id', where)
            if check:
                query = query.replace('ORDER BY', 'ORDER BY match_check DESC, aml_date DESC,')

        return query, params

    def _get_invoice_matching_query(self, st_lines_with_partner, excluded_ids):
        query, params = super(AccountReconcileModelUSA, self)._get_invoice_matching_query(
            st_lines_with_partner, excluded_ids)
        query, params = self._apply_conditions(query, params)
        return query, params

    def _get_check_matching_query(self, st_lines_with_partner, excluded_ids):
        """
        Prepare query for check matching
        - Check number on BSL label and payment must be the same
        - There's no need to have same payee
        """
        self.ensure_one()
        query = r'''
                SELECT
                    st_line.id                                  AS id,
                    aml.id                                      AS aml_id,
                    aml.currency_id                             AS aml_currency_id,
                    aml.date_maturity                           AS aml_date_maturity,
                    CASE 
                        WHEN st_line.check_number_cal IS NOT NULL AND st_line.check_number_cal = payment.check_number THEN 1 
                        ELSE 0 
                    END AS match_check,
                    TRUE                                        AS payment_reference_flag,
                    aml.amount_residual                         AS aml_amount_residual,
                    aml.amount_residual_currency                AS aml_amount_residual_currency
                FROM account_bank_statement_line st_line
                JOIN account_move st_line_move                  ON st_line_move.id = st_line.move_id    
                JOIN res_company company                        ON company.id = st_line_move.company_id
                , account_move_line aml
                LEFT JOIN account_move move                     ON move.id = aml.move_id AND move.state = 'posted'
                LEFT JOIN account_account account               ON account.id = aml.account_id
                LEFT JOIN account_payment payment               ON payment.move_id = move.id
                WHERE
                    aml.company_id = st_line_move.company_id        
                    AND move.state = 'posted'
                    AND account.reconcile IS TRUE
                    AND aml.reconciled IS FALSE
                '''

        # Add conditions to handle each of the statement lines we want to match
        st_lines_queries = []
        for st_line in st_lines_with_partner:
            check_st = r" AND st_line.amount = aml.balance AND st_line.check_number_cal IS NOT NULL AND st_line.check_number_cal = payment.check_number"
            if st_line.amount > 0:
                st_line_subquery = r"aml.balance > 0" + check_st
            else:
                st_line_subquery = r"aml.balance < 0" + check_st

            if self.match_same_currency:
                st_line_subquery += r" AND COALESCE(aml.currency_id, company.currency_id) = %s" % (
                    st_line.foreign_currency_id.id or st_line.move_id.currency_id.id)

            st_lines_queries.append(
                r"st_line.id = %s AND (%s)" % (st_line.id, st_line_subquery))

        query += r" AND (%s) " % " OR ".join(st_lines_queries)

        params = {}

        if self.past_months_limit:
            date_limit = fields.Date.context_today(self) - relativedelta(months=self.past_months_limit)
            query += "AND aml.date >= %(aml_date_limit)s"
            params['aml_date_limit'] = date_limit

        # Filter out excluded account.move.line.
        if excluded_ids:
            query += 'AND aml.id NOT IN %(excluded_aml_ids)s'
            params['excluded_aml_ids'] = tuple(excluded_ids)

        if self.matching_order == 'new_first':
            query += ' ORDER BY aml_date_maturity DESC, aml_id DESC'
        else:
            query += ' ORDER BY aml_date_maturity ASC, aml_id ASC'
        query, params = self._apply_conditions(query, params, check=True)

        return query, params

    def _get_candidates(self, st_lines_with_partner, excluded_ids):
        """
        Override
        Get matching check payments and append to candidate list
        """
        self.ensure_one()
        rslt = super(AccountReconcileModelUSA, self)._get_candidates(st_lines_with_partner, excluded_ids)

        # Check matching
        if self.rule_type == 'invoice_matching':
            st_check_lines = [st for st, partner in st_lines_with_partner if st.check_number_cal]
            if st_check_lines:
                query, params = self._get_check_matching_query(st_check_lines, excluded_ids)
                self._cr.execute(query, params)

                res = defaultdict(lambda: [])
                for candidate_dict in self._cr.dictfetchall():
                    res[candidate_dict['id']].append(candidate_dict)

                for key, val in res.items():
                    rslt[key] = val

        return rslt

    def _apply_rules(self, st_lines, excluded_ids=None, partner_map=None):
        """
        Override
        If bank statement lines are reconciled automatically when applying bank rules, update their statuses
        """
        results = super(AccountReconcileModelUSA, self)._apply_rules(st_lines, excluded_ids, partner_map)
        to_update_st_lines = st_lines.filtered(lambda r: not r.amount_residual and r.status == 'open')
        # Mark BSL as reviewed
        to_update_st_lines.write({'status': 'confirm'})
        # Mark all the lines that are not Bank or Bank Suspense Account temporary_reconcile
        to_update_st_lines.get_reconciliation_lines().write({'temporary_reconciled': True})

        return results
