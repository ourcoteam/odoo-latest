# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ========== Fields ==========
    
    volume = fields.Float(
        string="Volume",
        digits='Volume',
        help="Volume - used to calculate quantity automatically. "
             "Quantity = (Volume × Number of Panels) / 100,000,000"
    )
    
    number_of_panels = fields.Float(
        string="Number of Panels",
        digits='Product Unit',
        default=0.0,
        help="Number of panels - used to calculate quantity automatically. "
             "Quantity = (Volume × Number of Panels) / 100,000,000"
    )

    # ========== Compute Methods ==========

    @api.depends('volume', 'number_of_panels')
    def _compute_product_uom_qty(self):
        """
        Calculate product_uom_qty automatically based on:
        Quantity = (Volume × Number of Panels) / 100,000,000
        
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
    def _onchange_product_id_set_volume(self):
        """
        Set default volume from product when product is selected.
        """
        if self.product_id and self.product_id.volume:
            self.volume = self.product_id.volume

    # ========== Override Methods ==========

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use it directly in financial calculations.
        """
        # product_uom_qty is already calculated correctly, use it as-is
        return super()._prepare_base_line_for_taxes_computation(**kwargs)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_ids', 'volume', 'number_of_panels')
    def _compute_amount(self):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use the standard calculation.
        """
        # product_uom_qty is already calculated correctly, use standard calculation
        super()._compute_amount()

    def _prepare_invoice_line(self, **optional_values):
        """
        Override: product_uom_qty is already calculated automatically,
        so we just use it directly in invoice line.
        """
        # product_uom_qty is already calculated correctly, use it as-is
        res = super()._prepare_invoice_line(**optional_values)
        # Add volume and panels information in description (optional)
        if res.get('name') and self.volume and self.number_of_panels:
            res['name'] = f"{res['name']}\nVolume: {self.volume}, Panels: {self.number_of_panels}"
        return res
