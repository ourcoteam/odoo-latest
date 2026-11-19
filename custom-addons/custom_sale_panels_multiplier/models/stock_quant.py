# -*- coding: utf-8 -*-

from odoo import models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, qty=0):
        quants = super()._gather(product_id, location_id, lot_id=lot_id, package_id=package_id,
                                 owner_id=owner_id, strict=strict, qty=qty)
        # Set by stock.move._update_reserved_quantity_vals for a package quoted
        # on the sale line: Odoo would also take stock without a lot.
        only_lot_id = self.env.context.get('panels_reserve_lot_id')
        if only_lot_id:
            quants = quants.filtered(lambda quant: quant.lot_id.id == only_lot_id)
        return quants
