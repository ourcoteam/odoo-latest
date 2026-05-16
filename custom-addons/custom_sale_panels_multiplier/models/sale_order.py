# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    show_volume = fields.Boolean(
        string="إظهار Volume",
        default=True,
        help="Enable to show Volume field in order lines.",
    )
