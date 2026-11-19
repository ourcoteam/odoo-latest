# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def get_import_templates(self):
        # Timber template first, in the user's language: its headers are the
        # field labels, so the import maps every column by itself.
        suffix = '_ar' if (self.env.lang or '').startswith('ar') else ''
        return [{
            'label': _("Timber Quotations Import Template"),
            'template': f'/custom_sale_panels_multiplier/static/xls/quotation_template_timber{suffix}.xlsx',
        }] + super().get_import_templates()

    show_volume = fields.Boolean(
        string="Show Volume",
        default=True,
        help="Enable to show Volume field in order lines.",
    )

    total_qty_m3 = fields.Float(
        string="Total Quantity m³",
        compute='_compute_total_qty_m3',
        digits='Panels Quantity m3',
    )

    @api.depends('order_line.product_uom_qty', 'order_line.display_type', 'order_line.is_downpayment')
    def _compute_total_qty_m3(self):
        for order in self:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and not l.is_downpayment
            )
            order.total_qty_m3 = sum(lines.mapped('product_uom_qty'))
