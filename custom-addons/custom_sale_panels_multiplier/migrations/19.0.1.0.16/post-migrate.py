# -*- coding: utf-8 -*-
# Products built with the new naming (they have a wood type) got the same name
# in every language. Rebuild them now that the values have Arabic names.
# Older products keep their name until they are edited, as before.

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    templates = env['product.template'].with_context(active_test=False).search(
        [('kind_id', '!=', False)]
    )
    for template in templates:
        template._panels_apply_auto_name()
