# -*- coding: utf-8 -*-

from odoo import fields, models

from .product_product import _panels_format_dimension_number


class StockMove(models.Model):
    _inherit = 'stock.move'

    supplier_company_id = fields.Many2one(
        related='product_id.product_tmpl_id.supplier_company_id',
        string="الشركة المورّدة",
        store=True,
    )

    def _panels_load_sheet_line(self):
        """Values of one row of the driver load sheet: panels, description
        with the order line sizes, and m³ (what is loaded, else what is planned)."""
        self.ensure_one()
        qty = self.quantity or self.product_uom_qty
        # sale_line_id comes from sale_stock, which is not a dependency.
        sale_line = self.sale_line_id if 'sale_line_id' in self._fields else self.env['sale.order.line']
        panels = 0
        sizes = ''
        if sale_line:
            if sale_line.number_of_panels and sale_line.product_uom_qty:
                # Partial deliveries get their share of the ordered panels.
                panels = round(sale_line.number_of_panels * qty / sale_line.product_uom_qty)
            dims = [_panels_format_dimension_number(self.env, value)
                    for value in (sale_line.length, sale_line.width, sale_line.thickness)]
            if all(dims):
                sizes = 'طول %s - عرض %s - سمك %s' % tuple(dims)
        return {
            'panels': panels,
            'product': self.product_id.with_context(lang=self.env.lang).display_name,
            'sizes': sizes,
            'qty': qty,
            'uom': self.product_uom.name,
        }
