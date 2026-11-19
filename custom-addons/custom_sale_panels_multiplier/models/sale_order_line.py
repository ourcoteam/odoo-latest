# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DIVISOR = 100000000.0  # 100 million: length (cm) × width (mm) × thickness (mm) → m³


def _panels_qty_from_dimensions(length, width, thickness, number_of_panels):
    """Quantity in m³, or None when a size or the panels are missing."""
    if length and width and thickness and number_of_panels and number_of_panels > 0:
        return (length * width * thickness * number_of_panels) / DIVISOR
    return None


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_uom_qty = fields.Float(digits='Panels Quantity m3')

    # ========== Fields ==========

    panels_lot_id = fields.Many2one(
        'stock.lot',
        string="Package No.",
        domain="[('product_id', '=?', product_id), ('product_id.tracking', '=', 'lot'), ('product_qty', '>', 0)]",
        check_company=True,
        index='btree_not_null',
        # A package is sold once: a duplicated quotation must not quote it again.
        copy=False,
        help="The supplier's package (bundle) number, tracked in stock as a lot. "
             "Confirming the order reserves this package on the delivery.",
    )

    length = fields.Float(
        string="Length",
        digits='Panels Millimeter',
        help="Length - used to calculate volume. Volume = Length × Width × Thickness"
    )

    width = fields.Float(
        string="Width",
        digits='Panels Millimeter',
        help="Width - used to calculate volume. Volume = Length × Width × Thickness"
    )

    thickness = fields.Float(
        string="Thickness",
        digits='Panels Millimeter',
        help="Thickness - used to calculate volume. Volume = Length × Width × Thickness"
    )

    supplier_company_id = fields.Many2one(
        related='product_id.product_tmpl_id.supplier_company_id',
        string="Supplier Company",
        store=True,
    )

    volume = fields.Float(
        string="Volume",
        compute='_compute_volume',
        store=True,
        # Precomputed so the quantity, price and amounts that depend on it can
        # be precomputed too: a line created without a price (import, API)
        # would otherwise be inserted with an empty price and fail.
        precompute=True,
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
        if self.panels_lot_id and self.panels_lot_id.product_id != self.product_id:
            self.panels_lot_id = False

    @api.onchange('panels_lot_id')
    def _onchange_panels_lot_id(self):
        """Choosing a package brings its product (and the product's sizes)."""
        product = self.panels_lot_id.product_id
        if product and product != self.product_id:
            self.product_id = product
            self.width = product.width or 0.0
            self.thickness = product.thickness or 0.0

    # ========== Constraints ==========

    @api.constrains('panels_lot_id', 'product_id')
    def _check_panels_lot_product(self):
        for line in self:
            if line.panels_lot_id and line.panels_lot_id.product_id != line.product_id:
                raise ValidationError(_(
                    "Package %(package)s belongs to the product %(package_product)s, not to %(product)s.",
                    package=line.panels_lot_id.name,
                    package_product=line.panels_lot_id.product_id.display_name,
                    product=line.product_id.display_name,
                ))

    # ========== Create ==========

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('display_type'):
                self._panels_prepare_create_vals(vals)
        return super().create(vals_list)

    @api.model
    def _panels_prepare_create_vals(self, vals):
        """Complete a new line like the form does on screen, for lines that do
        not come from the form (Excel import, API): the package's product, the
        product's sizes and the m³ quantity. The form already sends all of them,
        with the same values."""
        Lot = self.env['stock.lot']
        if vals.get('panels_lot_id'):
            lot = Lot.browse(vals['panels_lot_id'])
            if not vals.get('product_id'):
                # The import matched the package by its number alone.
                if Lot.search_count([('name', '=', lot.name), ('id', '!=', lot.id)], limit=1):
                    raise ValidationError(_(
                        "Package %s exists for more than one product: fill in the product too.",
                        lot.name,
                    ))
                vals['product_id'] = lot.product_id.id
            elif lot.product_id.id != vals['product_id']:
                # Same package number for another product: take that product's package.
                order = self.env['sale.order'].browse(vals.get('order_id'))
                company = order.company_id or self.env.company
                same_name = Lot.search([
                    ('name', '=', lot.name),
                    ('product_id', '=', vals['product_id']),
                    ('company_id', 'in', [company.id, False]),
                ], limit=1)
                if same_name:
                    vals['panels_lot_id'] = same_name.id
            # The form only offers packages in stock; the import matches any name.
            lot = Lot.browse(vals['panels_lot_id'])
            if self.env.context.get('import_file') and lot.product_qty <= 0:
                raise ValidationError(_("Package %s has no stock left.", lot.name))
        product = self.env['product.product'].browse(vals.get('product_id'))
        # An empty imported cell arrives as False; an API call may leave the sizes out.
        fill_empty = self.env.context.get('import_file')
        for field_name in ('width', 'thickness'):
            if (field_name not in vals or (fill_empty and not vals[field_name])) and product[field_name]:
                vals[field_name] = product[field_name]
        # The quantity's default (1) would otherwise win over the sizes.
        qty = _panels_qty_from_dimensions(
            vals.get('length'), vals.get('width'), vals.get('thickness'), vals.get('number_of_panels'))
        if qty is not None:
            vals['product_uom_qty'] = qty

    # ========== Packages ==========

    def _panels_package_names(self):
        """Package numbers of this line: the ones delivered, else the quoted one."""
        self.ensure_one()
        lots = self.env['stock.lot']
        if 'move_ids' in self._fields:  # sale_stock is installed but not a dependency
            delivered = self.move_ids.filtered(
                lambda move: move.state == 'done' and move.location_dest_id.usage == 'customer')
            lots = delivered.move_line_ids.lot_id
        return ', '.join((lots or self.panels_lot_id).mapped('name'))

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
        packages = self._panels_package_names()
        if res.get('name') and packages:
            res['name'] = f"{res['name']}\n" + _("Package No.: %s", packages)
        return res
