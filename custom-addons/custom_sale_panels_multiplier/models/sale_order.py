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

    @api.model
    def load(self, fields, data):
        if 'order_line/panels_lot_id' in fields and 'order_line/product_id' in fields:
            self._panels_create_new_packages(fields, data)
        return super().load(fields, data)

    @api.model
    def _panels_create_new_packages(self, fields, data):
        """A package number not in Odoo yet, on a row that names its product, is a
        package quoted before it arrives: create it for that product, so the import
        finds it. The receipt that brings it under the same number fills it.
        The import screen's Test button rolls this back with the rest."""
        lot_col, product_col = fields.index('order_line/panels_lot_id'), fields.index('order_line/product_id')
        Lot, Product = self.env['stock.lot'], self.env['product.product']
        for row in data:
            name = (row[lot_col] if lot_col < len(row) else '') or ''
            product_name = (row[product_col] if product_col < len(row) else '') or ''
            if not isinstance(name, str) or not name.strip() or not isinstance(product_name, str) or not product_name.strip():
                continue
            name = name.strip()
            products = Product.browse([pid for pid, _label in Product.name_search(product_name.strip(), operator='=', limit=2)])
            if len(products) != 1 or products.tracking != 'lot':
                continue  # the import reports the product (or the tracking) itself
            # A number already used (for this product or another one) is matched as it is:
            # another product's number on the row is reported as a mismatch, not created again.
            if not Lot.search_count([('name', '=', name), ('company_id', 'in', [self.env.company.id, False])], limit=1):
                Lot.create({'name': name, 'product_id': products.id, 'company_id': self.env.company.id})
            row[lot_col] = name

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
