# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    supplier_company_id = fields.Many2one(
        related='product_id.product_tmpl_id.supplier_company_id',
        string="الشركة المورّدة",
        store=True,
    )
