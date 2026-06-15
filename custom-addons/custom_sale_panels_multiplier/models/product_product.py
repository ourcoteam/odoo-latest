# -*- coding: utf-8 -*-
# product.product + product.template extensions in one module file so fields
# always load together (avoids upgrade errors if one file is missing on server).

from odoo import api, fields, models
from odoo.tools import float_round
from odoo.tools.float_utils import float_is_zero

PANELS_AUTO_NAME_FIELDS = frozenset({'mark', 'grade', 'width', 'thickness'})

def _panels_load_result_ids(load_result):
    """Extract ids from `load()` result across Odoo versions."""
    if not load_result:
        return []
    # Common: {'ids': [...], 'messages': [...]}
    if isinstance(load_result, dict):
        ids = load_result.get('ids') or []
        return [i for i in ids if i]
    # Some variants may return (ids, messages) or (ids, ...)
    if isinstance(load_result, (list, tuple)) and load_result:
        first = load_result[0]
        if isinstance(first, (list, tuple)):
            return [i for i in first if i]
    return []


def _panels_format_dimension_number(env, value):
    """Format width/thickness for the auto name; empty if unset or zero."""
    if value is False or value is None:
        return ''
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ''
    prec_digits = env['decimal.precision'].precision_get('Panels Millimeter')
    if prec_digits is None:
        prec_digits = 4
    rounded = float_round(v, precision_digits=prec_digits)
    if float_is_zero(rounded, precision_digits=prec_digits):
        return ''
    if float_is_zero(rounded - int(rounded), precision_digits=prec_digits + 4):
        return str(int(rounded))
    text = ('%%.%df' % prec_digits) % rounded
    return text.rstrip('0').rstrip('.')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Keep width/thickness canonical on product.template; expose on variant as editable related.
    width = fields.Float(
        related='product_tmpl_id.width',
        readonly=False,
        store=True,
        digits='Panels Millimeter',
    )

    thickness = fields.Float(
        related='product_tmpl_id.thickness',
        readonly=False,
        store=True,
        digits='Panels Millimeter',
    )

    # Keep mark/grade canonical on product.template; expose on variant as editable related.
    mark = fields.Char(
        related='product_tmpl_id.mark',
        readonly=False,
        store=True,
    )

    grade = fields.Char(
        related='product_tmpl_id.grade',
        readonly=False,
        store=True,
    )

    @api.onchange('mark', 'grade', 'width', 'thickness')
    def _onchange_panels_auto_name(self):
        if len(self.product_tmpl_id.product_variant_ids) != 1:
            return
        name = self.env['product.template']._panels_build_product_name(
            self.mark, self.grade, self.thickness, self.width
        )
        if name:
            self.name = name

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if PANELS_AUTO_NAME_FIELDS & vals.keys():
            templates = self.product_tmpl_id.filtered(lambda t: t.product_variant_count == 1)
            for tmpl in templates:
                tmpl.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return res

    def load(self, fields, data):
        """Ensure auto-name after Excel imports on variants."""
        res = super().load(fields, data)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if not (PANELS_AUTO_NAME_FIELDS & set(fields or [])):
            return res
        ids = _panels_load_result_ids(res)
        if not ids:
            return res
        templates = self.browse(ids).exists().mapped('product_tmpl_id')
        for tmpl in templates:
            tmpl.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Canonical fields (persist on template even with multiple variants)
    width = fields.Float(
        string="العرض",
        store=True,
        digits='Panels Millimeter',
        help="Product width - auto-fills in sale order line when product is selected."
    )

    thickness = fields.Float(
        string="السمك",
        store=True,
        digits='Panels Millimeter',
        help="Product thickness - auto-fills in sale order line when product is selected."
    )

    # Canonical fields (persist on template even with multiple variants)
    mark = fields.Char(
        string="Mark",
        help="Used with Grade, thickness and width to build the product name automatically."
    )

    grade = fields.Char(
        string="Grade",
        help="Used with Mark, thickness and width to build the product name automatically."
    )

    @api.model
    def _panels_build_product_name(self, mark, grade, thickness, width):
        """Build name as: Mark - Grade - T - W (non-empty parts only)."""
        parts = []
        m = (mark or '').strip()
        if m:
            parts.append(m)
        g = (grade or '').strip()
        if g:
            parts.append(g)
        t = _panels_format_dimension_number(self.env, thickness)
        if t:
            parts.append(t)
        w = _panels_format_dimension_number(self.env, width)
        if w:
            parts.append(w)
        return ' - '.join(parts) if parts else ''

    def _panels_apply_auto_name(self):
        self.ensure_one()
        name = self._panels_build_product_name(
            self.mark, self.grade, self.thickness, self.width
        )
        if not name:
            return
        self.with_context(skip_panels_auto_name=True).write({'name': name})

    @api.onchange('mark', 'grade', 'width', 'thickness')
    def _onchange_panels_auto_name(self):
        name = self._panels_build_product_name(
            self.mark, self.grade, self.thickness, self.width
        )
        if name:
            self.name = name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_panels_auto_name'):
            for template in records:
                template.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if PANELS_AUTO_NAME_FIELDS & vals.keys():
            for template in self:
                template.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return res

    def load(self, fields, data):
        """Ensure auto-name during/after Excel imports on templates.

        Import of new products requires `name`. If the sheet omits `name` (or
        provides it blank), we auto-fill it from Mark/Grade/Thickness/Width
        before delegating to Odoo's import, then we also enforce auto-name after.
        """
        fields = list(fields or [])
        data = list(data or [])

        # Pre-fill required `name` for create imports when it is missing/blank.
        if PANELS_AUTO_NAME_FIELDS & set(fields):
            name_idx = fields.index('name') if 'name' in fields else None
            if name_idx is None:
                fields.append('name')
                name_idx = len(fields) - 1
                data = [list(row) + [''] for row in data]

            idx = {f: fields.index(f) for f in PANELS_AUTO_NAME_FIELDS if f in fields}
            builder = self.env['product.template']._panels_build_product_name

            for row in data:
                current = row[name_idx] if name_idx < len(row) else ''
                if isinstance(current, str) and current.strip():
                    continue
                if current not in (False, None, ''):
                    continue
                computed = builder(
                    row[idx.get('mark')] if 'mark' in idx else '',
                    row[idx.get('grade')] if 'grade' in idx else '',
                    row[idx.get('thickness')] if 'thickness' in idx else '',
                    row[idx.get('width')] if 'width' in idx else '',
                )
                row[name_idx] = computed or 'Imported Product'

        res = super().load(fields, data)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if not (PANELS_AUTO_NAME_FIELDS & set(fields or [])):
            return res
        ids = _panels_load_result_ids(res)
        if not ids:
            return res
        templates = self.browse(ids).exists()
        for tmpl in templates:
            tmpl.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return res
