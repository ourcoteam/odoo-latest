# -*- coding: utf-8 -*-
# Driver / loading details typed on each delivery, printed on the driver's
# load sheet ("Load Sheet (No Prices)"). Spec: Odoo Requirements OAG, page 9.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    panels_driver_name = fields.Char(string="Driver Name")
    panels_vehicle_plate = fields.Char(string="Car Plate")
    panels_driver_license = fields.Char(string="Driver's Licence No.")
    panels_reviewer = fields.Char(string="Reviewer")
    panels_warehouse_keeper = fields.Char(string="Warehouse Keeper")
