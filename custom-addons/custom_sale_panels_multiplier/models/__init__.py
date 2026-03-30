# -*- coding: utf-8 -*-

# product_product defines both product.product and product.template (same file = safe load order).
from . import product_product
from . import purchase_order_line
from . import sale_order_line
