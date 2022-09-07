from odoo.tools import formatLang


def format_currency(self, value):
    currency = self.env.company.currency_id
    return_value = formatLang(self.env, currency.round(value) + 0.0, currency_obj=currency)
    return return_value