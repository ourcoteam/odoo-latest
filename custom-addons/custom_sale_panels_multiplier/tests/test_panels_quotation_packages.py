# -*- coding: utf-8 -*-
# Quotations from Excel and packages (lots) quoted on the sale line:
# m³ computed on import, the package brings its product, the delivery reserves
# that package only, and the package shows on the invoice and the load sheet.

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPanelsQuotationPackages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env.user.group_ids |= cls.env.ref('stock.group_production_lot')
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.customer = cls.env['res.partner'].create({'name': 'Panels Test Customer'})
        cls.vendor = cls.env['res.partner'].create({'name': 'Panels Test Vendor'})
        cls.kind = cls.env['panels.product.kind'].create({'name': 'Panels Test Wood', 'uses_drying': False})
        cls.redwood = cls._timber(25.0, 100.0)            # 25x100, lots
        cls.fillery = cls._timber(75.0, 75.0)             # 75x75, lots
        cls.plain = cls._timber(38.0, 100.0, tracking='none')

    @classmethod
    def _timber(cls, thickness, width, tracking='lot'):
        return cls.env['product.template'].create({
            'type': 'consu',
            'is_storable': True,
            'tracking': tracking,
            'kind_id': cls.kind.id,
            'drying': 'none',
            'thickness': thickness,
            'width': width,
            'invoice_policy': 'delivery',
        }).product_variant_id

    def _lot(self, name, product, qty, days_old=0):
        lot = self.env['stock.lot'].create({'name': name, 'product_id': product.id, 'company_id': self.company.id})
        if qty:
            self.env['stock.quant']._update_available_quantity(
                product, self.stock, qty, lot_id=lot,
                in_date=fields.Datetime.now() - timedelta(days=days_old))
        return lot

    def _order(self, *lines):
        return self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create(vals) for vals in lines],
        })

    def _import(self, fields_list, rows):
        return self.env['sale.order'].with_context(import_file=True).load(fields_list, rows)

    # ---------- quantity m³ on create / write ----------

    def test_create_line_computes_m3(self):
        order = self._order({'product_id': self.plain.id, 'length': 420, 'width': 100,
                             'thickness': 25, 'number_of_panels': 420, 'price_unit': 100})
        self.assertAlmostEqual(order.order_line.product_uom_qty, 4.41, places=6)
        self.assertAlmostEqual(order.amount_untaxed, 441.0, places=2)

    def test_sizes_win_over_a_typed_quantity(self):
        # Same rule as the form, where the quantity is read-only once the sizes are set.
        order = self._order({'product_id': self.plain.id, 'product_uom_qty': 9, 'length': 420,
                             'width': 100, 'thickness': 25, 'number_of_panels': 420})
        self.assertAlmostEqual(order.order_line.product_uom_qty, 4.41, places=6)

    def test_line_without_sizes_keeps_its_quantity(self):
        order = self._order({'product_id': self.plain.id, 'product_uom_qty': 5, 'width': 0, 'thickness': 0},
                            {'product_id': self.plain.id, 'width': 0, 'thickness': 0})
        self.assertEqual(order.order_line.mapped('product_uom_qty'), [5.0, 1.0])

    def test_missing_sizes_come_from_the_product(self):
        order = self._order({'product_id': self.redwood.id, 'length': 420, 'number_of_panels': 420})
        line = order.order_line
        self.assertEqual((line.thickness, line.width), (25.0, 100.0))
        self.assertAlmostEqual(line.product_uom_qty, 4.41, places=6)

    def test_sizes_typed_as_zero_stay_zero_outside_import(self):
        order = self._order({'product_id': self.redwood.id, 'length': 420, 'width': 0,
                             'thickness': 0, 'number_of_panels': 420})
        self.assertEqual(order.order_line.width, 0.0)
        self.assertEqual(order.order_line.product_uom_qty, 1.0)

    def test_write_sizes_updates_m3(self):
        order = self._order({'product_id': self.plain.id, 'length': 420, 'width': 100,
                             'thickness': 25, 'number_of_panels': 420})
        order.order_line.write({'length': 600, 'number_of_panels': 484})
        self.assertAlmostEqual(order.order_line.product_uom_qty, 7.26, places=6)

    def test_form_line_with_package(self):
        lot = self._lot('PKG-FORM', self.redwood, 4.41)
        with Form(self.env['sale.order']) as order_form:
            order_form.partner_id = self.customer
            with order_form.order_line.new() as line:
                line.panels_lot_id = lot
                self.assertEqual(line.product_id, self.redwood)
                self.assertEqual((line.thickness, line.width), (25.0, 100.0))
                line.length = 420
                line.number_of_panels = 420
                self.assertAlmostEqual(line.product_uom_qty, 4.41, places=6)
        order = order_form.record
        self.assertEqual(order.order_line.panels_lot_id, lot)
        self.assertAlmostEqual(order.order_line.product_uom_qty, 4.41, places=6)

    def test_form_changing_product_clears_package(self):
        lot = self._lot('PKG-CLEAR', self.redwood, 4.41)
        with Form(self.env['sale.order']) as order_form:
            order_form.partner_id = self.customer
            with order_form.order_line.new() as line:
                line.panels_lot_id = lot
                line.product_id = self.fillery
                self.assertFalse(line.panels_lot_id)
                self.assertEqual((line.thickness, line.width), (75.0, 75.0))

    # ---------- Excel import ----------

    def test_import_quotation_like_the_client_file(self):
        self._lot('KEIT14004584', self.redwood, 7.26)
        self._lot('BIND26511431', self.redwood, 4.73)
        fields_list = ['partner_id', 'client_order_ref', 'order_line/panels_lot_id', 'order_line/product_id',
                       'order_line/thickness', 'order_line/width', 'order_line/length',
                       'order_line/number_of_panels', 'order_line/price_unit']
        rows = [
            [self.customer.name, 'Card 7877', 'KEIT14004584', '', '', '', '600', '484', '19025'],
            ['', '', 'BIND26511431', '', '', '', '420', '1', '16825'],
            ['', '', 'BIND26511431', '', '', '', '450', '419', '16825'],
            ['', '', '', self.fillery.display_name, '75', '75', '300', '182', '17825'],
        ]
        result = self._import(fields_list, rows)
        self.assertFalse(result['messages'], result['messages'])
        order = self.env['sale.order'].browse(result['ids'])
        lines = order.order_line
        self.assertEqual(lines.mapped('product_id'), self.redwood | self.fillery)
        self.assertEqual([line.panels_lot_id.name for line in lines],
                         ['KEIT14004584', 'BIND26511431', 'BIND26511431', False])
        self.assertEqual(lines.mapped('thickness'), [25.0, 25.0, 25.0, 75.0])
        self.assertEqual(lines.mapped('width'), [100.0, 100.0, 100.0, 75.0])
        for line, qty in zip(lines, [7.26, 0.0105, 4.71375, 3.07125]):
            self.assertAlmostEqual(line.product_uom_qty, qty, places=6)
        self.assertAlmostEqual(order.total_qty_m3, 15.0555, places=6)
        for line, subtotal in zip(lines, [138121.50, 176.66, 79308.84, 54745.03]):
            self.assertAlmostEqual(line.price_subtotal, subtotal, places=2)
        # Odoo rounds the order total from the unrounded line amounts.
        self.assertAlmostEqual(order.amount_untaxed, 272352.04, places=2)

    def test_import_package_and_product_that_do_not_match(self):
        self._lot('PKG-RW', self.redwood, 4.41)
        result = self._import(
            ['partner_id', 'order_line/panels_lot_id', 'order_line/product_id', 'order_line/length',
             'order_line/number_of_panels'],
            [[self.customer.name, 'PKG-RW', self.fillery.display_name, '420', '420']])
        self.assertFalse(result['ids'])
        self.assertIn('PKG-RW', result['messages'][0]['message'])

    def test_import_same_package_number_for_two_products(self):
        self._lot('PKG-SAME', self.redwood, 4.41)
        fillery_lot = self._lot('PKG-SAME', self.fillery, 4.41)
        fields_list = ['partner_id', 'order_line/panels_lot_id', 'order_line/product_id',
                       'order_line/length', 'order_line/number_of_panels']
        # With the product: that product's package.
        result = self._import(fields_list, [[self.customer.name, 'PKG-SAME', self.fillery.display_name, '300', '10']])
        self.assertFalse([m for m in result['messages'] if m['type'] == 'error'], result['messages'])
        self.assertEqual(self.env['sale.order'].browse(result['ids']).order_line.panels_lot_id, fillery_lot)
        # Without the product: refused, the package number alone is ambiguous.
        result = self._import(fields_list, [[self.customer.name, 'PKG-SAME', '', '300', '10']])
        self.assertFalse(result['ids'])
        self.assertTrue(any('PKG-SAME' in m['message'] for m in result['messages']))

    def test_line_without_price_gets_the_product_price(self):
        self.redwood.list_price = 123.0
        order = self._order({'product_id': self.redwood.id, 'length': 420, 'number_of_panels': 420})
        self.assertEqual(order.order_line.price_unit, 123.0)
        self.assertAlmostEqual(order.amount_untaxed, 4.41 * 123.0, places=2)

    def test_import_unknown_package_is_refused(self):
        result = self._import(['partner_id', 'order_line/panels_lot_id', 'order_line/length',
                               'order_line/number_of_panels'],
                              [[self.customer.name, 'NO-SUCH-PKG', '420', '420']])
        self.assertFalse(result['ids'])

    def _sell_out(self, lot):
        order = self._order({'panels_lot_id': lot.id, 'product_id': lot.product_id.id,
                             'product_uom_qty': lot.product_qty, 'width': 0, 'thickness': 0})
        order.action_confirm()
        order.picking_ids.button_validate()
        self.assertEqual(order.picking_ids.state, 'done')
        self.assertAlmostEqual(lot.product_qty, 0.0, places=2)

    def _receive(self, product, packages):
        purchase = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [Command.create({'product_id': product.id, 'product_qty': sum(packages.values()),
                                           'width': 0, 'thickness': 0, 'price_unit': 50})],
        })
        purchase.button_confirm()
        receipt = purchase.picking_ids
        move = receipt.move_ids
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create([{
            'move_id': move.id, 'picking_id': receipt.id, 'product_id': product.id,
            'product_uom_id': move.product_uom.id, 'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id, 'lot_name': name, 'quantity': qty,
        } for name, qty in packages.items()])
        move.picked = True
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
        return receipt

    def test_import_sold_out_package_is_refused(self):
        self._sell_out(self._lot('PKG-SOLD', self.redwood, 4.41))
        result = self._import(['partner_id', 'order_line/panels_lot_id', 'order_line/length',
                               'order_line/number_of_panels'],
                              [[self.customer.name, 'PKG-SOLD', '420', '420']])
        self.assertFalse(result['ids'])
        self.assertTrue(any('PKG-SOLD' in m['message'] for m in result['messages']), result['messages'])

    def test_duplicated_quotation_does_not_copy_the_package(self):
        lot = self._lot('PKG-COPY', self.redwood, 4.41)
        order = self._order({'panels_lot_id': lot.id, 'product_id': self.redwood.id,
                             'length': 420, 'number_of_panels': 420})
        copy = order.copy()
        self.assertFalse(copy.order_line.panels_lot_id)
        self.assertEqual(copy.order_line.product_id, self.redwood)
        self.assertAlmostEqual(copy.order_line.product_uom_qty, 4.41, places=6)

    def test_import_section_and_note_lines(self):
        result = self._import(
            ['partner_id', 'order_line/display_type', 'order_line/name', 'order_line/product_id',
             'order_line/length', 'order_line/number_of_panels'],
            [[self.customer.name, 'line_section', 'Card 7877', '', '', ''],
             ['', '', 'Redwood 25x100', self.redwood.display_name, '420', '420']])
        self.assertFalse(result['messages'], result['messages'])
        lines = self.env['sale.order'].browse(result['ids']).order_line
        self.assertEqual(lines.mapped('display_type'), ['line_section', False])
        self.assertAlmostEqual(lines[1].product_uom_qty, 4.41, places=6)

    def test_line_package_of_another_product_is_refused(self):
        lot = self._lot('PKG-OTHER', self.redwood, 4.41)
        with self.assertRaises(ValidationError):
            self._order({'product_id': self.fillery.id, 'panels_lot_id': lot.id, 'length': 300,
                         'number_of_panels': 10})

    # ---------- delivery reserves the quoted package ----------

    def test_confirm_reserves_the_quoted_package(self):
        self._lot('PKG-A', self.redwood, 4.41, days_old=10)   # FIFO would take this one
        lot_b = self._lot('PKG-B', self.redwood, 4.41)
        order = self._order({'panels_lot_id': lot_b.id, 'product_id': self.redwood.id,
                             'length': 420, 'number_of_panels': 420, 'price_unit': 100})
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertEqual(move.move_line_ids.lot_id, lot_b)
        self.assertAlmostEqual(move.quantity, 4.41, places=2)
        order.picking_ids.button_validate()
        self.assertEqual(order.picking_ids.state, 'done')
        self.assertAlmostEqual(lot_b.product_qty, 0.0, places=2)
        self.assertAlmostEqual(self.env['stock.lot'].search([('name', '=', 'PKG-A')]).product_qty, 4.41, places=2)
        # The invoice carries the delivered package.
        invoice = order._create_invoices()
        self.assertIn('PKG-B', invoice.invoice_line_ids.name)

    def test_line_without_package_reserves_as_before(self):
        lot_a = self._lot('PKG-A2', self.redwood, 4.41, days_old=10)
        self._lot('PKG-B2', self.redwood, 4.41)
        order = self._order({'product_id': self.redwood.id, 'length': 420, 'number_of_panels': 420})
        order.action_confirm()
        self.assertEqual(order.picking_ids.move_ids.move_line_ids.lot_id, lot_a)

    def test_quoted_package_short_is_not_completed_from_another(self):
        self._lot('PKG-BIG', self.redwood, 10.0, days_old=10)
        lot_small = self._lot('PKG-SMALL', self.redwood, 2.0)
        self.env['stock.quant']._update_available_quantity(self.redwood, self.stock, 3.0)  # stock without a lot
        order = self._order({'panels_lot_id': lot_small.id, 'product_id': self.redwood.id,
                             'length': 420, 'number_of_panels': 420})
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertEqual(move.move_line_ids.lot_id, lot_small)
        self.assertAlmostEqual(move.quantity, 2.0, places=2)
        # Check Availability again: still only that package.
        order.picking_ids.action_assign()
        self.assertEqual(move.move_line_ids.lot_id, lot_small)
        self.assertAlmostEqual(move.quantity, 2.0, places=2)

    def test_two_lines_sharing_one_package(self):
        lot = self._lot('BIND-MIX', self.redwood, 4.73)
        order = self._order(
            {'panels_lot_id': lot.id, 'product_id': self.redwood.id, 'length': 420, 'number_of_panels': 1},
            {'panels_lot_id': lot.id, 'product_id': self.redwood.id, 'length': 450, 'number_of_panels': 419})
        order.action_confirm()
        moves = order.picking_ids.move_ids
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves.move_line_ids.lot_id, lot)
        self.assertAlmostEqual(sum(moves.mapped('quantity')), 4.72, places=2)

    def test_product_without_lots_is_untouched(self):
        self.env['stock.quant']._update_available_quantity(self.plain, self.stock, 10.0)
        order = self._order({'product_id': self.plain.id, 'length': 420, 'width': 100, 'thickness': 25,
                             'number_of_panels': 420})
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertAlmostEqual(move.quantity, 4.41, places=2)
        order.picking_ids.button_validate()
        self.assertEqual(order.picking_ids.state, 'done')

    # ---------- receipt with packages, then sale of one package ----------

    def test_receive_packages_then_sell_one(self):
        purchase = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [Command.create({'product_id': self.redwood.id, 'length': 420, 'width': 100,
                                           'thickness': 25, 'number_of_panels': 840, 'price_unit': 50})],
        })
        self.assertAlmostEqual(purchase.order_line.product_qty, 8.82, places=6)
        purchase.button_confirm()
        receipt = purchase.picking_ids
        move = receipt.move_ids
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create([{
            'move_id': move.id, 'picking_id': receipt.id, 'product_id': self.redwood.id,
            'product_uom_id': move.product_uom.id, 'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id, 'lot_name': name, 'quantity': 4.41,
        } for name in ('RCV-1', 'RCV-2')])
        move.picked = True
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
        lot_2 = self.env['stock.lot'].search([('name', '=', 'RCV-2'), ('product_id', '=', self.redwood.id)])
        self.assertAlmostEqual(lot_2.product_qty, 4.41, places=2)
        result = self._import(['partner_id', 'order_line/panels_lot_id', 'order_line/length',
                               'order_line/number_of_panels', 'order_line/price_unit'],
                              [[self.customer.name, 'RCV-2', '420', '420', '100']])
        order = self.env['sale.order'].browse(result['ids'])
        order.action_confirm()
        self.assertEqual(order.picking_ids.move_ids.move_line_ids.lot_id, lot_2)

    # ---------- packages quoted before they arrive ----------

    def test_quote_package_before_it_arrives(self):
        # Typed on screen once the product is chosen (many2one quick create with the line product).
        lot_id, _name = self.env['stock.lot'].with_context(
            default_product_id=self.redwood.id, default_company_id=self.company.id).name_create('FUT-1')
        lot = self.env['stock.lot'].browse(lot_id)
        self.assertTrue(lot.panels_quotable)
        self.assertIn(lot, self.env['stock.lot'].search([('panels_quotable', '=', True)]))
        order = self._order({'panels_lot_id': lot.id, 'product_id': self.redwood.id,
                             'length': 420, 'number_of_panels': 420, 'price_unit': 100})
        self.assertAlmostEqual(order.order_line.product_uom_qty, 4.41, places=6)
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertFalse(move.move_line_ids)
        # The packing list brings it under the same number: same lot, and the delivery reserves it.
        self._lot('FUT-OTHER', self.redwood, 5.0)  # another package in stock is never taken
        self._receive(self.redwood, {'FUT-1': 4.41, 'FUT-2': 3.0})
        self.assertEqual(self.env['stock.lot'].search_count(
            [('name', '=', 'FUT-1'), ('product_id', '=', self.redwood.id)]), 1)
        self.assertAlmostEqual(lot.product_qty, 4.41, places=2)
        self.assertEqual(move.move_line_ids.lot_id, lot)
        self.assertAlmostEqual(move.quantity, 4.41, places=2)
        order.picking_ids.button_validate()
        self.assertEqual(order.picking_ids.state, 'done')
        lot.invalidate_recordset()
        self.assertFalse(lot.panels_quotable)  # delivered: it cannot be quoted again

    def test_import_package_before_it_arrives(self):
        fields_list = ['partner_id', 'order_line/panels_lot_id', 'order_line/product_id',
                       'order_line/length', 'order_line/number_of_panels', 'order_line/price_unit']
        result = self._import(fields_list, [
            [self.customer.name, 'FUT-IMP', self.redwood.display_name, '420', '420', '100'],
            ['', 'FUT-IMP', self.redwood.display_name, '450', '10', '100'],
        ])
        self.assertFalse([m for m in result['messages'] if m['type'] == 'error'], result['messages'])
        lines = self.env['sale.order'].browse(result['ids']).order_line
        lot = self.env['stock.lot'].search([('name', '=', 'FUT-IMP')])
        self.assertEqual(len(lot), 1)
        self.assertEqual(lines.panels_lot_id, lot)
        self.assertEqual(lot.product_id, self.redwood)
        self.assertAlmostEqual(lines[0].product_uom_qty, 4.41, places=6)
        # Without the product the new number is unknown.
        result = self._import(['partner_id', 'order_line/panels_lot_id', 'order_line/length',
                               'order_line/number_of_panels'],
                              [[self.customer.name, 'FUT-NO-PRODUCT', '420', '420']])
        self.assertFalse(result['ids'])
        self.assertFalse(self.env['stock.lot'].search([('name', '=', 'FUT-NO-PRODUCT')]))

    def test_package_on_product_not_tracked_is_refused(self):
        lot = self.env['stock.lot'].create({'name': 'PLAIN-1', 'product_id': self.plain.id,
                                            'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self._order({'panels_lot_id': lot.id, 'product_id': self.plain.id, 'length': 420,
                         'width': 100, 'thickness': 38, 'number_of_panels': 10})

    # ---------- products switched to package tracking ----------

    def test_track_by_package_keeps_the_stock_deliverable(self):
        product = self._timber(25.0, 125.0, tracking='none')
        self.env['stock.quant']._update_available_quantity(product, self.stock, 10.0)
        order = self._order({'product_id': product.id, 'length': 420, 'number_of_panels': 420})  # 5.5125 m3
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertAlmostEqual(move.quantity, 5.51, places=2)
        result = product.product_tmpl_id.action_panels_track_by_package()
        self.assertEqual(result['params']['type'], 'success')
        self.assertEqual(product.tracking, 'lot')
        old = self.env['stock.lot'].search([('product_id', '=', product.id)])
        self.assertEqual(len(old), 1)
        self.assertAlmostEqual(old.product_qty, 10.0, places=2)
        self.assertEqual(move.move_line_ids.lot_id, old)  # the open reservation is redone on it
        self.assertAlmostEqual(move.quantity, 5.51, places=2)
        order.picking_ids.button_validate()  # a tracked product: Odoo needs a lot, it has one
        self.assertEqual(order.picking_ids.state, 'done')
        self.assertAlmostEqual(old.product_qty, 10.0 - move.quantity, places=2)
        # New packages arrive as usual and are quoted by number.
        self._receive(product, {'NEW-PKG': 3.0})
        new = self.env['stock.lot'].search([('name', '=', 'NEW-PKG')])
        self.assertAlmostEqual(new.product_qty, 3.0, places=2)
        # Running it twice changes nothing.
        product.product_tmpl_id.action_panels_track_by_package()
        self.assertEqual(self.env['stock.lot'].search_count([('product_id', '=', product.id)]), 2)

    # ---------- documents ----------

    def test_package_on_quotation_and_load_sheet(self):
        lot = self._lot('PKG-PRINT', self.redwood, 4.41)
        order = self._order({'panels_lot_id': lot.id, 'product_id': self.redwood.id,
                             'length': 420, 'number_of_panels': 420})
        html = self.env['ir.actions.report']._render_qweb_html('sale.action_report_saleorder', order.ids)[0]
        self.assertIn(b'PKG-PRINT', html)
        order.action_confirm()
        picking = order.picking_ids
        self.assertEqual(picking.move_ids._panels_load_sheet_line()['packages'], 'PKG-PRINT')
        html = self.env['ir.actions.report']._render_qweb_html(
            'custom_sale_panels_multiplier.action_report_load_sheet', picking.ids)[0]
        self.assertIn(b'PKG-PRINT', html)

    def test_import_template_is_offered(self):
        self.env['res.lang']._activate_lang('ar_001')
        templates = self.env['sale.order'].with_context(lang='ar_001').get_import_templates()
        self.assertTrue(templates[0]['template'].endswith('quotation_template_timber_ar.xlsx'))
        templates = self.env['sale.order'].with_context(lang='en_US').get_import_templates()
        self.assertTrue(templates[0]['template'].endswith('quotation_template_timber.xlsx'))
        self.assertTrue(any(t['template'] == '/sale/static/xls/quotations_import_template.xlsx' for t in templates))
