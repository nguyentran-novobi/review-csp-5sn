# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2021 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import models, fields, api, _


class Module(models.Model):
    _inherit = 'ir.module.module'
    
    def module_uninstall(self):
        # Unlink all action windows using for viewing audit logs
        audit_trail_module = self.filtered(lambda module: module.name == "novobi_audit_trail")
        if audit_trail_module:
            act_view_log = self.env['ir.actions.act_window'].sudo().search([('res_model', '=', 'audit.trail.log')])
            if act_view_log:
                act_view_log.unlink()
        return super(Module, self).module_uninstall()
