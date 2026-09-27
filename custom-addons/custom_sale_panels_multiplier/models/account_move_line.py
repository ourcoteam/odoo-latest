# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    width = fields.Float(
        string="العرض",
        digits='Panels Millimeter',
    )

    thickness = fields.Float(
        string="السمك",
        digits='Panels Millimeter',
    )

    @api.onchange('product_id')
    def _onchange_product_id_set_dimensions(self):
        """Copy width and thickness from product when product is selected."""
        if self.product_id:
            self.width = self.product_id.width or 0.0
            self.thickness = self.product_id.thickness or 0.0
