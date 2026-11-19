# -*- coding: utf-8 -*-

from odoo import _, fields, models

from .product_product import _panels_format_dimension_number


class StockMove(models.Model):
    _inherit = 'stock.move'

    supplier_company_id = fields.Many2one(
        related='product_id.product_tmpl_id.supplier_company_id',
        string="Supplier Company",
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
                sizes = _("Length %(length)s - Width %(width)s - Thickness %(thickness)s",
                          length=dims[0], width=dims[1], thickness=dims[2])
        lots = self.move_line_ids.lot_id or sale_line.panels_lot_id
        return {
            'panels': panels,
            'product': self.product_id.with_context(lang=self.env.lang).display_name,
            'sizes': sizes,
            'packages': ', '.join(lots.mapped('name')),
            'qty': qty,
            'uom': self.product_uom.name,
        }

    # ========== Packages (lots) quoted on the sale line ==========

    def _panels_quoted_lot(self):
        """The package chosen on the sale line, when this move takes the goods
        out of stock (not for receipts, returns or products without lots)."""
        self.ensure_one()
        if 'sale_line_id' not in self._fields:
            return self.env['stock.lot']
        lot = self.sale_line_id.panels_lot_id
        if (lot and lot.product_id == self.product_id and self.product_id.tracking == 'lot'
                and self.location_id.usage == 'internal'):
            return lot
        return self.env['stock.lot']

    def _update_reserved_quantity_vals(self, need, location_id, lot_id=None, package_id=None, owner_id=None, strict=True):
        lot = self.env['stock.lot'] if lot_id else self._panels_quoted_lot()
        if not lot:
            return super()._update_reserved_quantity_vals(
                need, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=strict)
        # Reserve the quoted package only: neither another package nor stock
        # without a package (see stock.quant._gather).
        move = self.with_context(panels_reserve_lot_id=lot.id)
        return super(StockMove, move)._update_reserved_quantity_vals(
            need, location_id, lot_id=lot, package_id=package_id, owner_id=owner_id, strict=strict)
