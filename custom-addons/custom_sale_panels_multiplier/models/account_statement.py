# -*- coding: utf-8 -*-

from odoo import api, fields, models

# A partner's statement only makes sense on receivable/payable accounts
# (what the customer owes us / what we owe the vendor) - same account types
# core Odoo uses to compute res.partner.credit/debit/total_due.
STATEMENT_ACCOUNT_TYPES = ('asset_receivable', 'liability_payable')


class AccountStatementWizard(models.TransientModel):
    _name = 'account.statement.wizard'
    _description = "Statement of Account"

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one(
        'res.partner', required=True, string="العميل / المورد",
    )
    date_from = fields.Date(string="من تاريخ")
    date_to = fields.Date(string="إلى تاريخ", default=fields.Date.context_today)

    opening_balance = fields.Monetary(compute='_compute_statement')
    closing_balance = fields.Monetary(compute='_compute_statement')
    line_ids = fields.One2many(
        'account.statement.wizard.line', 'wizard_id',
        string="الحركات", compute='_compute_statement',
    )

    def _get_move_line_domain(self):
        self.ensure_one()
        return [
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', STATEMENT_ACCOUNT_TYPES),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
        ]

    @api.depends('partner_id', 'date_from', 'date_to', 'company_id')
    def _compute_statement(self):
        AccountMoveLine = self.env['account.move.line']
        for wizard in self:
            if not wizard.partner_id:
                wizard.opening_balance = 0.0
                wizard.closing_balance = 0.0
                wizard.line_ids = [(5, 0, 0)]
                continue

            base_domain = wizard._get_move_line_domain()

            opening_balance = 0.0
            if wizard.date_from:
                opening_result = AccountMoveLine._read_group(
                    base_domain + [('date', '<', wizard.date_from)],
                    aggregates=['balance:sum'],
                )
                opening_balance = opening_result[0][0] or 0.0
            wizard.opening_balance = opening_balance

            range_domain = base_domain
            if wizard.date_from:
                range_domain = range_domain + [('date', '>=', wizard.date_from)]
            if wizard.date_to:
                range_domain = range_domain + [('date', '<=', wizard.date_to)]
            move_lines = AccountMoveLine.search(range_domain, order='date, id')

            running_balance = opening_balance
            line_commands = [(5, 0, 0)]
            for move_line in move_lines:
                running_balance += move_line.balance
                line_commands.append((0, 0, {
                    'date': move_line.date,
                    'move_id': move_line.move_id.id,
                    'label': move_line.name or move_line.move_id.name or '',
                    'debit': move_line.debit,
                    'credit': move_line.credit,
                    'balance': running_balance,
                }))
            wizard.line_ids = line_commands
            wizard.closing_balance = running_balance

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'custom_sale_panels_multiplier.action_report_account_statement'
        ).report_action(self)


class AccountStatementWizardLine(models.TransientModel):
    _name = 'account.statement.wizard.line'
    _description = "Statement of Account Line"
    _order = 'date, id'

    wizard_id = fields.Many2one(
        'account.statement.wizard', required=True, ondelete='cascade',
    )
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    date = fields.Date(string="التاريخ")
    move_id = fields.Many2one('account.move', string="القيد")
    label = fields.Char(string="البيان")
    debit = fields.Monetary(string="مدين")
    credit = fields.Monetary(string="دائن")
    balance = fields.Monetary(string="الرصيد الجاري")
