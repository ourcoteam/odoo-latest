# -*- coding: utf-8 -*-

# product_product defines both product.product and product.template (same file = safe load order).
from . import product_product
from . import account_move_line
from . import account_statement
from . import purchase_order
from . import purchase_order_line
from . import sale_order
from . import sale_order_line
from . import sale_report
from . import stock_move
