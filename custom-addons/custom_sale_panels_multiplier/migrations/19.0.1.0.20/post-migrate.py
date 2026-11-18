# -*- coding: utf-8 -*-
# Wood types and origins get the spec rules (which name parts each wood type
# has, origins per wood type, grades per origin). Set them once here; after
# that they are maintained from the configuration lists.

from odoo import SUPERUSER_ID, api

from odoo.addons.custom_sale_panels_multiplier.models.panels_mark_grade import panels_apply_spec_rules


def migrate(cr, version):
    panels_apply_spec_rules(api.Environment(cr, SUPERUSER_ID, {}))
