# -*- coding: utf-8 -*-
# Packages (lots) on quotations: a package can be quoted while it is in stock,
# and before it arrives (created from the quotation, received later under the
# same number); a package that was in stock and is now gone cannot.

from odoo import _, api, fields, models
from odoo.fields import Domain


class StockLot(models.Model):
    _inherit = 'stock.lot'

    panels_quotable = fields.Boolean(
        string="Can Be Quoted",
        compute='_compute_panels_quotable',
        search='_search_panels_quotable',
        help="In stock, or not received yet (no stock move done with it).",
    )

    def _panels_moved_lot_ids(self):
        groups = self.env['stock.move.line'].sudo()._read_group(
            [('state', '=', 'done'), ('lot_id', '!=', False)], ['lot_id'])
        return {lot.id for (lot,) in groups}

    @api.depends('product_qty')
    def _compute_panels_quotable(self):
        moved = self._panels_moved_lot_ids() if self.ids else set()
        for lot in self:
            lot.panels_quotable = lot.product_qty > 0 or lot.id not in moved

    def _search_panels_quotable(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        domain = Domain('product_qty', '>', 0) | Domain('id', 'not in', list(self._panels_moved_lot_ids()))
        return domain if (operator == '=') == value else ~domain


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_panels_track_by_package(self):
        """Products list > Action > Track by Package: track the selected goods
        by lot, and label the stock they already have as one lot "Old Stock"
        per product, so it can still be delivered (Odoo asks a lot for every
        delivery of a tracked product). Nothing is moved: quantities, values
        and history stay; open reservations are redone on the new lot."""
        templates = self.filtered(lambda t: t.type == 'consu' and t.is_storable)
        products = templates.product_variant_ids
        Quant = self.env['stock.quant'].sudo()
        quants = Quant.search([
            ('product_id', 'in', products.ids),
            ('location_id.usage', 'in', ('internal', 'transit')),
            ('lot_id', '=', False),
        ])
        lines = self.env['stock.move.line'].sudo().search([
            ('product_id', 'in', products.ids),
            ('lot_id', '=', False),
            ('state', 'not in', ('done', 'cancel')),
            ('location_id.usage', 'in', ('internal', 'transit')),
        ])
        moves = lines.move_id
        moves._do_unreserve()
        templates.filtered(lambda t: t.tracking != 'lot').write({'tracking': 'lot'})
        Lot = self.env['stock.lot'].sudo()
        old_name = _("Old Stock")
        lots = {}
        for quant in quants:
            key = (quant.product_id.id, quant.company_id.id)
            if key not in lots:
                lots[key] = Lot.search([
                    ('name', '=', old_name), ('product_id', '=', quant.product_id.id),
                    ('company_id', 'in', [quant.company_id.id, False]),
                ], limit=1) or Lot.create({
                    'name': old_name, 'product_id': quant.product_id.id, 'company_id': quant.company_id.id,
                })
            # A relabel, not a stock move: no valuation or history change.
            quant.write({'lot_id': lots[key].id})
        moves._action_assign()
        # A second step (e.g. Input -> Stock) reserves what its first step brought, under the
        # lot that step had (none): reserve it on the Old Stock package instead.
        chained = self.env['stock.move'].sudo().search([
            ('product_id', 'in', products.ids),
            ('state', 'in', ('confirmed', 'partially_available')),
            ('move_orig_ids', '!=', False),
            ('location_id.usage', 'in', ('internal', 'transit')),
        ])
        for move in chained:
            old = Lot.search([
                ('name', '=', old_name), ('product_id', '=', move.product_id.id),
                ('company_id', 'in', [move.company_id.id, False]),
            ], limit=1)
            missing = move.product_qty - move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id)
            if old and missing > 0:
                move._update_reserved_quantity(missing, move.location_id, lot_id=old, strict=False)
        chained._recompute_state()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _(
                    "%(products)s products are now tracked by package; the stock of %(old)s of them "
                    "is in the package \"%(name)s\".",
                    products=len(templates), old=len({key[0] for key in lots}), name=old_name,
                ),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
