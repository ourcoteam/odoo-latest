# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    width = fields.Float(
        string="العرض",
        digits='Volume',
        help="Product width - auto-fills in sale order line when product is selected."
    )

    thickness = fields.Float(
        string="السمك",
        digits='Volume',
        help="Product thickness - auto-fills in sale order line when product is selected."
    )
