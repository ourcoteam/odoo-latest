# -*- coding: utf-8 -*-
# The value names (wood type, origin, sawmill, grade, sub-type) become
# translatable, so their column turns into jsonb. The unique indexes on
# lower(name) cannot survive that type change: drop them here, the module
# recreates them on the English name.

TABLES = (
    'panels_product_kind',
    'panels_product_origin',
    'panels_product_mark',
    'panels_product_grade',
    'panels_product_subtype',
)


def migrate(cr, version):
    for table in TABLES:
        cr.execute(f'DROP INDEX IF EXISTS {table}_name_uniq')
