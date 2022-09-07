from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date, get_lang


class AccountFollowupDepositReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_lines(self, options, line_id=None):
        """
        Override to add deposit table
        """
        lines = super(AccountFollowupDepositReport, self)._get_lines(options, line_id)

        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        lang_code = partner.lang if self._context.get('print_mode') else self.env.user.lang or get_lang(self.env).code

        res = {}
        line_num = 0
        columns = []
        align_right_style = 'text-align:right; white-space:nowrap;'
        for line in partner.customer_deposit_aml_ids:
            if line.company_id == self.env.company:
                if self.env.context.get('print_mode') and line.blocked:
                    continue
                currency = line.currency_id or line.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(line)

        for currency, aml_recs in res.items():
            total = 0
            # Add deposit transaction lines
            for line in aml_recs:
                if self.env.context.get('print_mode') and line.blocked:
                    continue

                amount = line.currency_id and line.amount_residual_currency or line.amount_residual
                total += not line.blocked and amount or 0
                amount = formatLang(self.env, amount, currency_obj=currency)
                columns = [
                    format_date(self.env, line.date, lang_code=lang_code),
                    {'name': line.move_id.ref, 'style': align_right_style},
                    {'name': '', 'blocked': line.blocked},
                    {'name': amount, 'style': align_right_style}
                ]

                if self.env.context.get('print_mode'):
                    columns = columns[:2] + columns[3:]

                line_num += 1
                lines.append({
                    'id': line.id,
                    'account_move': line.move_id,
                    'deposit_line': True,
                    'name': line.move_id.name,
                    'caret_options': 'followup',
                    'move_id': line.move_id.id,
                    'unfoldable': False,
                    'columns': [type(v) == dict and v or {'name': v} for v in columns],
                })

            # Add Total Deposit line
            total_due = formatLang(self.env, total, currency_obj=currency)
            line_num += 1
            total_deposit_columns = [{'name': v} for v in [''] * (self.env.context.get('print_mode') and 1 or 2)]
            total_deposit_columns += [
                {'name': _('Total Deposit'), 'style': align_right_style},
                {'name': total_due, 'style': align_right_style
            }]
            lines.append({
                'id': line_num,
                'name': '',
                'deposit_line': True,
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': total_deposit_columns,
            })

            # Add an empty line after the total deposit to make a space between two currencies
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'deposit_line': True,
                'class': '',
                'style': 'border-bottom-style: none',
                'unfoldable': False,
                'level': 0,
                'columns': [{}] * len(columns),
            })

        # Remove the empty line after last deposit table
        if lines and res:
            lines.pop()

        return lines

    def _get_deposit_columns_name(self):
        headers = [
            {'name': _('Deposit'), 'style': 'text-align:left; white-space:nowrap;'},
            {'name': _('Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
            {'name': _('Communication'), 'style': 'text-align:right; white-space:nowrap;'},
            {'name': _('Excluded'), 'class': 'date', 'style': 'white-space:nowrap;'},
            {'name': _('Total'), 'class': 'number o_price_total', 'style': 'text-align:right; white-space:nowrap;'}
        ]
        if self.env.context.get('print_mode'):
            headers = headers[:3] + headers[4:]  # Remove 'Excluded' column
        return headers

    def get_html(self, options, line_id=None, additional_context=None):
        """
        Override to add deposit columns header to additional context when rendering followup report
        """
        if not additional_context:
            additional_context = {}
        additional_context['deposit_columns_header'] = self._get_deposit_columns_name()

        return super(AccountFollowupDepositReport, self).get_html(options, line_id=line_id, additional_context=additional_context)
