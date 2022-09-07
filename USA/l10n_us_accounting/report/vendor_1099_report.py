# -*- coding: utf-8 -*-

from odoo import models, api, _
import ast


class ReportVendor1099(models.AbstractModel):
    _name = "vendor.1099.report"
    _description = "Vendor 1099 Report"
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'date_from': '', 'date_to': '', 'filter': 'this_year'}

    def _get_columns_name(self, options):
        return [
            {'name': _('Name')},
            {'name': _('EIN/SSN Number')},
            {'name': _('Address')},
            {'name': _('Amount Paid'), 'class': 'number'}
        ]

    def _get_templates(self):
        templates = super(ReportVendor1099, self)._get_templates()
        templates['main_template'] = 'l10n_us_accounting.template_usa_1099_report'
        return templates

    def _get_report_name(self):
        return _('Vendor 1099 Report')

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        partners = self._get_result_lines(options)

        total_amount = 0
        for p in partners:
            vals = {
                'id': p['partner_odoo_id'],
                'name': p['partner_name'],
                'level': 2,
                'caret_options': 'vendor.1099',
                'columns': [{'name': v} for v in [p['partner_ssn'],
                                                  p['partner_address'],
                                                  self.format_value(p['total_balance'])]],
            }
            lines.append(vals)
            total_amount += p['total_balance']

        total_line = {
            'id': 'total.amount.1099',
            'name': _('Total'),
            'level': 2,
            'class': 'total',
            'columns': [{'name': ''}, {'name': ''}, {'name': self.format_value(total_amount), 'class': 'number'}],
        }
        lines.append(total_line)
        return lines

    def _get_result_lines(self, options):
        cr = self.env.cr
        query_move_line = self._get_move_lines_query_statement(options, {'eligible_filter': True,
                                                                         'id': options.get('partner_id_filter')})
        query = """
            SELECT *
            FROM (
                SELECT partner_odoo_id, partner_name, partner_ssn, partner_address,
                        partner_street_address_print, partner_city_address_print,
                        SUM((debit - credit) * matched_percentage)  as total_balance
                FROM ({}) as result_table
                GROUP BY partner_odoo_id, partner_ssn, partner_address, partner_name, 
                    partner_street_address_print, partner_city_address_print
                ORDER BY UPPER(partner_name)
            ) as final_result
            WHERE total_balance != 0;
        """.format(query_move_line)

        cr.execute(query)

        partners = cr.dictfetchall()
        return partners

    def _get_move_lines_query_statement(self, options, params={}):
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        company_ids = self.env.context.get('company_ids', (self.env.company.id,))
        partner_filter = ''
        eligible_filter = ''
        payment_eligible_filter = ''
        if params:
            if params.get('id'):
                partner_filter = """AND aml.partner_id = {}""".format(params['id'])
            if params.get('eligible_filter'):
                eligible_filter = """AND aml.eligible_for_1099 = True"""
                payment_eligible_filter = "AND aml3.eligible_for_1099 = True"
        query_stmt = """
            SELECT move_line.payment_move_line_id AS line_id,
                aml.partner_id AS partner_odoo_id,
                partner.name AS partner_name,
                partner.vat AS partner_ssn,
                CONCAT(partner.street, ' ', partner.street2, ' ', partner.city, ' ', res_country_state.code, ' ', partner.zip) AS partner_address, 
                CONCAT(partner.street, ' ', partner.street2) AS partner_street_address_print,
                CONCAT(partner.city, ', ', res_country_state.code, ' ', partner.zip) AS partner_city_address_print,
                aml.debit, 
                aml.credit,
                CASE 
                    WHEN move_line.is_payment = FALSE THEN 1
                    ELSE (move_line.reconciled_amount / ABS(am.amount_total_signed))
                END AS matched_percentage
            FROM (
                SELECT move_line.move_line_id, move_line.payment_move_line_id, SUM(amount) AS reconciled_amount, move_line.eligible_for_1099, move_line.is_payment
                FROM (
                    SELECT apr.credit_move_id AS move_line_id, apr.amount AS amount, aml3.id AS payment_move_line_id, aml3.eligible_for_1099 AS eligible_for_1099, TRUE AS is_payment
                    FROM account_partial_reconcile apr
                        JOIN account_move_line aml3 ON apr.debit_move_id = aml3.id
                        JOIN account_move_line aml4 ON aml3.move_id = aml4.move_id
                        JOIN account_move_line aml5 ON apr.credit_move_id = aml5.id
                        JOIN account_journal aj ON aml4.journal_id = aj.id
                        JOIN account_move AS am2 ON aml4.move_id = am2.id
                        JOIN res_company AS company ON company.id = aj.company_id
                        LEFT JOIN account_payment AS ap ON aml4.payment_id = ap.id                    
                        LEFT JOIN account_payment_method_line AS apml ON apml.id = ap.payment_method_line_id
                    WHERE am2.state = 'posted'
                        AND aml4.account_id IN (apml.payment_account_id, company.account_journal_payment_credit_account_id)
                        AND (apml.is_credit_card IS NOT TRUE OR apml.id IS NULL)
                        AND aml5.statement_id IS NULL
                        {payment_eligible_filter}
                        
                    UNION
                    SELECT apr.debit_move_id AS move_line_id, apr.amount AS amount, aml3.id AS payment_move_line_id, aml3.eligible_for_1099 AS eligible_for_1099, TRUE AS is_payment
                    FROM account_partial_reconcile apr
                        JOIN account_move_line aml3 ON apr.credit_move_id = aml3.id
                        JOIN account_move_line aml4 ON aml3.move_id = aml4.move_id
                        JOIN account_move_line aml5 ON apr.debit_move_id = aml5.id
                        JOIN account_journal aj ON aml4.journal_id = aj.id
                        JOIN account_move AS am2 ON aml4.move_id = am2.id
                        JOIN res_company AS company ON company.id = aj.company_id
                        LEFT JOIN account_payment AS ap ON aml4.payment_id = ap.id                    
                        LEFT JOIN account_payment_method_line AS apml ON apml.id = ap.payment_method_line_id
                    WHERE am2.state = 'posted'                       
                        AND aml4.account_id IN (apml.payment_account_id, company.account_journal_payment_debit_account_id)
                        AND (apml.is_credit_card IS NOT TRUE OR apml.id IS NULL)
                        AND aml5.statement_id IS NULL
                        {payment_eligible_filter}
                          
                    UNION
                    SELECT aml4.id AS move_line_id, am2.amount_total AS amount, aml4.id AS payment_move_line_id, aml4.eligible_for_1099 AS eligible_for_1099, FALSE AS is_payment
                    FROM account_move_line aml3
                        JOIN account_move AS am2 ON aml3.move_id = am2.id
                        JOIN account_move_line aml4 ON am2.id = aml4.move_id
                        JOIN account_account AS aa3 ON aml3.account_id = aa3.id
                        JOIN account_account AS aa4 ON aml4.account_id = aa4.id
                        JOIN account_account_type AS aat ON aa3.user_type_id = aat.id
                        JOIN account_journal aj ON aml3.journal_id = aj.id
                        JOIN res_company AS company ON company.id = aj.company_id
                        LEFT JOIN account_payment AS ap ON aml3.payment_id = ap.id
                        LEFT JOIN account_payment_method_line AS apml ON apml.id = ap.payment_method_line_id
                    WHERE am2.state = 'posted'
                        AND ((
                                aml3.account_id IN (
                                    apml.payment_account_id, 
                                    company.account_journal_payment_debit_account_id, 
                                    company.account_journal_payment_credit_account_id
                                )
                                AND ap.id IS NOT NULL
                            )
                            OR (aat.type = 'liquidity' AND aat.internal_group = 'asset'))
                        AND (apml.is_credit_card IS NOT TRUE OR apml.id IS NULL)
                        AND aml3.id != aml4.id
                        AND aa4.account_eligible_1099 = TRUE
                        AND aa4.reconcile = FALSE
                ) as move_line
                GROUP BY move_line.move_line_id, move_line.payment_move_line_id, move_line.eligible_for_1099, move_line.is_payment
            ) as move_line
                JOIN account_move_line aml2 ON aml2.id = move_line.move_line_id
                JOIN account_move AS am ON aml2.move_id = am.id
                JOIN account_move_line AS aml ON aml2.move_id = aml.move_id AND (move_line.is_payment = FALSE AND aml2.id = aml.id OR move_line.is_payment = TRUE) 
                JOIN res_partner AS partner ON aml.partner_id = partner.id
                JOIN account_account AS aa ON aml.account_id = aa.id
                LEFT JOIN res_country_state ON partner.state_id = res_country_state.id
                          
            WHERE am.state = 'posted'
                AND aa.account_eligible_1099 = TRUE
                AND aa.reconcile = FALSE
                AND aml.date >= '{date_from}' AND aml.date <= '{date_to}'
                AND partner.vendor_eligible_1099 = TRUE
                AND aml.company_id IN ({company_ids})
                {partner_filter}
                {eligible_filter}
        """.format(date_from=date_from, date_to=date_to,
                   company_ids=','.join(str(company) for company in company_ids),
                   partner_filter=partner_filter, eligible_filter=eligible_filter,
                   payment_eligible_filter=payment_eligible_filter)

        return query_stmt

    def open_vendor_1099(self, options, params):
        list_view = self.env.ref('l10n_us_accounting.view_move_line_tree_1099')
        search_view = self.env.ref('l10n_us_accounting.view_eligible_1099_search')
        action = {
            'name': 'Journal Items',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,pivot,graph,form,kanban',
            'view_type': 'list',
            'views': [[list_view.id, 'list'], [False, 'pivot'], [False, 'graph'], [False, 'form'], [False, 'kanban']],
            'search_view_id': [search_view.id, 'search'],
            'context': {'search_default_filter_eligible_1099_lines': 1},
            'target': 'current',
        }
        if params and params.get('id') and options:
            cr = self.env.cr
            query_stmt = self._get_move_lines_query_statement(options, params)
            cr.execute(query_stmt)
            lines = cr.dictfetchall()
            line_ids = [line['line_id'] for line in lines]
            action['domain'] = [('id', 'in', line_ids)]

        return action

    @api.model
    def open_all_vendor_transactions(self, options):
        if not options:
            return None
        cr = self.env.cr
        options = ast.literal_eval(options)
        query_stmt = self._get_move_lines_query_statement(options)
        cr.execute(query_stmt)
        lines = cr.dictfetchall()
        line_ids = [line['line_id'] for line in lines]
        list_view = self.env.ref('l10n_us_accounting.view_move_line_tree_1099')
        search_view = self.env.ref('l10n_us_accounting.view_eligible_1099_search')

        return {
            'name': _('All Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,pivot,graph,form,kanban',
            'view_type': 'list',
            'views': [[list_view.id, 'list'], [False, 'pivot'], [False, 'graph'], [False, 'form'], [False, 'kanban']],
            'search_view_id': [search_view.id, 'search'],
            'domain': [('id', 'in', line_ids)],
            'context': {'search_default_filter_eligible_1099_lines': 1,
                        'search_default_group_by_partner': 1},
            'target': 'current',
        }

    @api.model
    def _get_data_for_1099_form(self):
        options = self._get_options(None)
        options['partner_id_filter'] = self.ids and self.ids[0]
        partners = self._get_result_lines(options)
        if partners:
            company = self.env.company.partner_id
            partners[0].update({
                'payer_name': company.name,
                'payer_street_address': '{} {}'.format(company.street, company.street2 or ''),
                'payer_city_address': '{}, {} {}'.format(company.city, company.state_id.code, company.zip),
                'payer_tin': company.vat,
                'total_balance': self.format_value(partners[0]['total_balance'])
            })
        return partners

    def print_report_1099(self, options, params=None):
        """
        1099 form has three copies A, B and C
        Use data argument of report_action to pass the copy type when rendering report template
        If using this argument, "docs" in report template becomes empty recordset => need to pass "docids" and browse it when rendering
        """
        self = self.browse(params.get('id'))[0]
        action_report_1099 = self.env.ref('l10n_us_accounting.action_print_report_1099')
        return action_report_1099.report_action(self.ids, data={'copy': params.get('copy'), 'docids': self.ids})

    def _get_report_filename(self):
        self.ensure_one()
        return 'Report 1099 - {}'.format(self.env['res.partner'].browse(self.id).name)
