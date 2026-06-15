# -*- coding: utf-8 -*-

from odoo import api, fields, models

DIVISOR = 100000000.0  # 100 million


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_qty = fields.Float(digits='Panels Quantity m3')

    # ========== Fields ==========

    length = fields.Float(
        string="الطول",
        digits='Panels Millimeter',
        help="Length - used to calculate volume. Volume = Length × Width × Thickness"
    )

    width = fields.Float(
        string="العرض",
        digits='Panels Millimeter',
        help="Width - used to calculate volume. Volume = Length × Width × Thickness"
    )

    thickness = fields.Float(
        string="السمك",
        digits='Panels Millimeter',
        help="Thickness - used to calculate volume. Volume = Length × Width × Thickness"
    )

    volume = fields.Float(
        string="Volume",
        compute='_compute_volume',
        store=True,
        digits='Panels Quantity m3',
        help="Volume = Length × Width × Thickness. Used in quantity calculation."
    )

    number_of_panels = fields.Integer(
        string="Number of Panels",
        default=0,
        help="Number of panels - used to calculate quantity automatically. "
             "Quantity = (Volume × Number of Panels) / 100,000,000"
    )

    # ========== Compute Methods ==========

    @api.depends('length', 'width', 'thickness')
    def _compute_volume(self):
        """Calculate volume from length × width × thickness."""
        for line in self:
            if line.length and line.width and line.thickness:
                line.volume = line.length * line.width * line.thickness
            else:
                line.volume = 0.0

    # ========== Helper: compute product_qty from dimensions ==========

    def _get_product_qty_from_dimensions(self):
        """Return product_qty from (volume × number_of_panels) / 100M if valid."""
        self.ensure_one()
        if self.volume and self.number_of_panels and self.number_of_panels > 0:
            return (self.volume * self.number_of_panels) / DIVISOR
        return None

    # ========== Onchange Methods ==========

    @api.onchange('product_id')
    def _onchange_product_id_set_dimensions(self):
        """Copy width and thickness from product when product is selected."""
        if self.product_id:
            self.width = self.product_id.width or 0.0
            self.thickness = self.product_id.thickness or 0.0

    @api.onchange('length', 'width', 'thickness', 'number_of_panels')
    def _onchange_dimensions_set_product_qty(self):
        """Set product_qty when dimensions and number_of_panels are provided."""
        qty = self._get_product_qty_from_dimensions()
        if qty is not None:
            self.product_qty = qty

    # ========== Override: create / write ==========

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            qty = self._compute_product_qty_from_vals(vals)
            if qty is not None:
                vals['product_qty'] = qty
        return super().create(vals_list)

    def write(self, vals):
        dim_fields = {'length', 'width', 'thickness', 'number_of_panels'}
        if dim_fields & set(vals.keys()):
            for line in self:
                merged = {
                    'length': line.length, 'width': line.width,
                    'thickness': line.thickness, 'number_of_panels': line.number_of_panels,
                }
                merged.update(vals)
                qty = self._compute_product_qty_from_merged_vals(merged)
                if qty is not None:
                    super(PurchaseOrderLine, line).write({'product_qty': qty})
        return super().write(vals)

    @api.model
    def _compute_product_qty_from_vals(self, vals):
        """Compute product_qty from vals (for create)."""
        length = vals.get('length')
        width = vals.get('width')
        thickness = vals.get('thickness')
        number_of_panels = vals.get('number_of_panels', 0)
        if length and width and thickness and number_of_panels and number_of_panels > 0:
            volume = length * width * thickness
            return (volume * number_of_panels) / DIVISOR
        return None

    def _compute_product_qty_from_merged_vals(self, merged):
        """Compute product_qty from merged dict (for write). length/width/thickness or volume."""
        length = merged.get('length')
        width = merged.get('width')
        thickness = merged.get('thickness')
        number_of_panels = merged.get('number_of_panels', 0)
        if not (number_of_panels and number_of_panels > 0):
            return None
        if length and width and thickness:
            volume = length * width * thickness
            return (volume * number_of_panels) / DIVISOR
        return None

    # ========== Override: _prepare_account_move_line ==========

    def _prepare_account_move_line(self, move=False):
        """Add dimensions to bill line description (same as Sale invoice line)."""
        res = super()._prepare_account_move_line(move=move)
        if res.get('name') and self.volume and self.number_of_panels:
            dims = []
            if self.length:
                dims.append(f"L: {self.length}")
            if self.width:
                dims.append(f"W: {self.width}")
            if self.thickness:
                dims.append(f"T: {self.thickness}")
            if dims:
                res['name'] = f"{res['name']}\n" + ", ".join(dims) + f", Panels: {self.number_of_panels}"
        return res
