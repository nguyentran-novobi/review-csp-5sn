from odoo import api, fields, models, _

LOG_CREATE = 1
LOG_UPDATE = 2
LOG_DELETE = 3

LOG_MSG_CREATE = 'Payment method line has been created.'
LOG_MSG_UPDATE = 'Payment method line has been updated.'
LOG_MSG_DELETE = 'Payment method line has been deleted.'

class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'


    is_credit_card = fields.Boolean(string='Is Credit Card Method?')

    def _track_msg_change_account_id(self, line,  values):
        if 'payment_account_id' in values:
            account_name = self.env['account.account'].browse(values['payment_account_id']).name
            new_account_name = '<i>None</i>' if not account_name else account_name
            old_account_name = '<i>None</i>' if not line.payment_account_id.name else line.payment_account_id.name
            msg = (_('Outstanding Account: ') +
                   '{} -> {} <br/>'.format(old_account_name, new_account_name))
        else:
            msg = (_('Outstanding Account: ') + '{}<br/>'.format(line.payment_account_id.name)
                   if line.payment_account_id.name else _('Outstanding Account: <i>None</i><br/>'))
                   
        return msg

    def _log_values(self, state, values):
        if state == LOG_CREATE and isinstance(values, list):
            string = LOG_MSG_CREATE
        elif state == LOG_UPDATE and 'payment_account_id' in values:
            string = LOG_MSG_UPDATE
            self = self.filtered(lambda r: r.payment_account_id.id != values['payment_account_id'])
        elif state == LOG_DELETE and not len(values):
            string = LOG_MSG_DELETE
        else:
            return
        journals = self.mapped('journal_id')
        for journal in journals:
            method_lines = self.filtered(lambda x: x.journal_id == journal)
            msg = '<b>' + _(string) + '</b><ul>'
            for line in method_lines:
                msg += (_('Payment Type: ') + '{}<br/>'.format(line.payment_type.title()))
                msg += (_('Payment Method: ') + '{}<br/>'.format(line.payment_method_id.name))
                msg += (_('Name: ') + '{}<br/>'.format(line.name)) if line.name else ''    
                msg += self._track_msg_change_account_id(line, values)
                msg += '<br/>'
            msg += '</ul>'
            journal.message_post(body=msg)
    
    def write(self, values):
        self._log_values(LOG_UPDATE, values)
        result = super().write(values)
        return result

    def create(self, values):
        result = super().create(values)
        result._log_values(LOG_CREATE, values)
        return result

    def unlink(self):
        self._log_values(LOG_DELETE, {})
        result = super().unlink()
        return result
