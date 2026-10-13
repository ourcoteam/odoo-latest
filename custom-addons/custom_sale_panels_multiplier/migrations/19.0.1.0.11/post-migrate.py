# -*- coding: utf-8 -*-
# Mark/Grade moved from free text (product_template.mark / .grade) to the
# saved lists panels.product.mark / panels.product.grade.
#
# Runs before Odoo drops the old columns (that happens at the end of the
# upgrade), so the old text is still readable here. Values that differ only
# by case/spacing become one list entry, spelled as most products had it.

import logging
from collections import Counter, defaultdict

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL, sql

_logger = logging.getLogger(__name__)

LEGACY_COLUMNS = (
    ('mark', 'mark_id', 'panels.product.mark'),
    ('grade', 'grade_id', 'panels.product.grade'),
)
BACKUP_TABLE = 'panels_legacy_mark_grade'


def migrate(cr, version):
    if not version:
        return
    present = [c for c in LEGACY_COLUMNS if sql.column_exists(cr, 'product_template', c[0])]
    if not present:
        return

    _backup_legacy_values(cr, [old for old, _new, _model in present])

    env = api.Environment(cr, SUPERUSER_ID, {})
    respelled = set()
    for old_col, new_field, model_name in present:
        cr.execute(SQL(
            "SELECT id, %(old)s FROM product_template"
            " WHERE %(new)s IS NULL AND NULLIF(TRIM(%(old)s), '') IS NOT NULL ORDER BY id",
            old=SQL.identifier(old_col), new=SQL.identifier(new_field),
        ))
        groups = defaultdict(list)
        for template_id, raw in cr.fetchall():
            clean = ' '.join(raw.split())
            groups[clean.lower()].append((template_id, raw, clean))

        Model = env[model_name]
        for rows in groups.values():
            spelling = Counter(clean for _id, _raw, clean in rows).most_common(1)[0][0]
            value = Model._panels_get_or_create(spelling)
            cr.execute(SQL(
                "UPDATE product_template SET %(new)s = %(value)s WHERE id = ANY(%(ids)s)",
                new=SQL.identifier(new_field), value=value.id, ids=[r[0] for r in rows],
            ))
            # The product name embeds the old text: rebuild it where the spelling changed.
            respelled.update(r[0] for r in rows if r[1].strip() != value.name)
        _logger.info("custom_sale_panels_multiplier: %s -> %s: %d values", old_col, model_name, len(groups))

    env.invalidate_all()
    templates = env['product.template'].with_context(active_test=False).browse(sorted(respelled))
    for template in templates.exists():
        template._panels_apply_auto_name()
    if respelled:
        _logger.info("custom_sale_panels_multiplier: renamed %d products after merging spellings", len(respelled))


def _backup_legacy_values(cr, columns):
    """Keep the old free-text values in a side table, since Odoo drops the columns."""
    if sql.table_exists(cr, BACKUP_TABLE):
        return
    cr.execute(SQL(
        "CREATE TABLE %(table)s AS SELECT id AS product_tmpl_id, %(cols)s, now() AS backed_up_at"
        " FROM product_template WHERE %(any_set)s",
        table=SQL.identifier(BACKUP_TABLE),
        cols=SQL(', ').join(SQL.identifier(c) for c in columns),
        any_set=SQL(' OR ').join(SQL('%s IS NOT NULL', SQL.identifier(c)) for c in columns),
    ))
