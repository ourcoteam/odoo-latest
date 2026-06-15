# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_uom_qty = fields.Float(digits='Panels Quantity m3')

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
        """
        Calculate volume from length × width × thickness.
        """
        for line in self:
            if line.length and line.width and line.thickness:
                line.volume = line.length * line.width * line.thickness
            else:
                line.volume = 0.0

    @api.depends('volume', 'number_of_panels')
    def _compute_product_uom_qty(self):
        """
        Calculate product_uom_qty automatically based on:
        Quantity = (Volume × Number of Panels) / 100,000,000
        Volume = Length × Width × Thickness

        If volume or number_of_panels is 0/empty, use default behavior.
        """
        # Call super first for display_type handling
        super()._compute_product_uom_qty()

        # Calculate quantity only if both volume and number_of_panels are provided
        DIVISOR = 100000000.0  # 100 million
        for line in self:
            if line.display_type:
                continue  # Already handled by super()

            if line.volume and line.number_of_panels and line.number_of_panels > 0:
                # Calculate quantity automatically
                line.product_uom_qty = (line.volume * line.number_of_panels) / DIVISOR
            # If volume or number_of_panels is missing/zero, keep default behavior
            # (user can still edit product_uom_qty manually)

    # ========== Onchange Methods ==========

    @api.onchange('product_id')
    def _onchange_product_id_set_dimensions(self):
        """
        Copy width and thickness from product when product is selected.
        Length is entered manually by the user.
        """
        if self.product_id:
            self.width = self.product_id.width or 0.0
            self.thickness = self.product_id.thickness or 0.0

    # ========== Override Methods ==========

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use it directly in financial calculations.
        """
        return super()._prepare_base_line_for_taxes_computation(**kwargs)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_ids', 'length', 'width', 'thickness', 'number_of_panels')
    def _compute_amount(self):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use the standard calculation.
        """
        super()._compute_amount()

    def _prepare_invoice_line(self, **optional_values):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use it directly in invoice line.
        """
        res = super()._prepare_invoice_line(**optional_values)
        # Add dimensions and panels information in description (optional)
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
