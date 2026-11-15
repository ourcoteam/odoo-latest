# -*- coding: utf-8 -*-
# Driver / loading details typed on each delivery, printed on the driver's
# load sheet (قسيمة صرف بدون أسعار). Spec: Odoo Requirements OAG, page 9.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    panels_driver_name = fields.Char(string="اسم السائق")
    panels_vehicle_plate = fields.Char(string="رقم السيارة")
    panels_driver_license = fields.Char(string="رقم رخصة القيادة")
    panels_reviewer = fields.Char(string="المراجع")
    panels_warehouse_keeper = fields.Char(string="أمين المخزن")
