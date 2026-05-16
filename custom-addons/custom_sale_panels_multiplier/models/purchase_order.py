# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    show_volume = fields.Boolean(
        string="إظهار Volume",
        default=True,
        help="Enable to show Volume field in order lines.",
    )
