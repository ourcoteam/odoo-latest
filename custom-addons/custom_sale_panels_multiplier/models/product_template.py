# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    width = fields.Float(
        string="العرض",
        compute='_compute_width',
        inverse='_set_width',
        store=True,
        digits='Volume',
        help="Product width - auto-fills in sale order line when product is selected."
    )

    thickness = fields.Float(
        string="السمك",
        compute='_compute_thickness',
        inverse='_set_thickness',
        store=True,
        digits='Volume',
        help="Product thickness - auto-fills in sale order line when product is selected."
    )

    @api.depends('product_variant_ids.width')
    def _compute_width(self):
        self._compute_template_field_from_variant_field('width')

    def _set_width(self):
        self._set_product_variant_field('width')

    @api.depends('product_variant_ids.thickness')
    def _compute_thickness(self):
        self._compute_template_field_from_variant_field('thickness')

    def _set_thickness(self):
        self._set_product_variant_field('thickness')
