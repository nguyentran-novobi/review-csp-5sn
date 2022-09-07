# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = "res.company"
    
    customer_payment_lead_time = fields.Integer(string='Due date for SO', default=30)
    vendor_payment_lead_time = fields.Integer(string='Due date for PO', default=30)
    cash_flow_period_number = fields.Integer(string='Number of period', default=6)
    cash_flow_last_period_type = fields.Selection(
        [('day', 'Daily'), ('week', 'Weekly'), ('month', 'Monthly')],
        string='Last selected period',
        default='month', required=True)
