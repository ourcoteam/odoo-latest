# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    show_volume = fields.Boolean(
        string="إظهار Volume",
        default=True,
        help="Enable to show Volume field in order lines.",
    )

    total_qty_m3 = fields.Float(
        string="إجمالي الكمية m³",
        compute='_compute_total_qty_m3',
        digits='Product Unit',
    )

    @api.depends('order_line.product_qty', 'order_line.display_type', 'order_line.is_downpayment')
    def _compute_total_qty_m3(self):
        for order in self:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and not l.is_downpayment
            )
            order.total_qty_m3 = sum(lines.mapped('product_qty'))
