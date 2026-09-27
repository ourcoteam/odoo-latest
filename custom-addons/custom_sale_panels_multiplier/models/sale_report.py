# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    supplier_company_id = fields.Many2one(
        'res.partner',
        string="الشركة المورّدة",
        readonly=True,
    )

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['supplier_company_id'] = "t.supplier_company_id"
        return res

    def _group_by_sale(self):
        return super()._group_by_sale() + ", t.supplier_company_id"
