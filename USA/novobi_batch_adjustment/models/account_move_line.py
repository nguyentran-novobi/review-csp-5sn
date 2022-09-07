from odoo import api, fields, models, _


class AccountMoveLineUSA(models.Model):
    _inherit = 'account.move.line'

    batch_fund_line_id = fields.Many2one('account.batch.deposit.fund.line',
                                         related='move_id.batch_fund_line_id', store=True)
