# -*- coding: utf-8 -*-
# product.product + product.template extensions in one module file so fields
# always load together (avoids upgrade errors if one file is missing on server).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL, float_round
from odoo.tools.float_utils import float_is_zero

from .panels_mark_grade import panels_clean_name

PANELS_IMPORT_VALUE_MODELS = (
    ('kind_id', 'panels.product.kind'),
    ('origin_id', 'panels.product.origin'),
    ('mark_id', 'panels.product.mark'),
    ('grade_id', 'panels.product.grade'),
    ('subtype_id', 'panels.product.subtype'),
)
PANELS_AUTO_NAME_FIELDS = frozenset(
    [field for field, _model in PANELS_IMPORT_VALUE_MODELS] + ['drying', 'width', 'thickness']
)
PANELS_DRYING_SELECTION = [('kd', 'KD (Kiln Dried)'), ('ad', 'AD (Air Dried)'), ('none', 'None')]
# Drying as written in the product name, per language (None is left out).
PANELS_DRYING_LABELS = {'kd': 'KD', 'ad': 'AD'}
PANELS_DRYING_LABELS_AR = {'kd': 'مجفف', 'ad': 'مبلل'}

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


def _panels_import_base_fields(fields):
    """Top-level field names of an import (`mark_id/id` -> `mark_id`)."""
    return {f.split('/')[0] for f in fields or []}


def _panels_prepare_import_rows(env, fields, data):
    """Normalize the timber columns of imported rows (in place).

    Odoo matches a Many2one cell by exact name only, so a sheet with a new
    value or a different case/spacing would fail. Reuse the saved value
    (unarchiving it if needed) or create it, and rewrite the cell to the
    stored spelling.
    """
    if 'drying' in fields:
        # Accept KD / AD / None in any case; an empty cell means None.
        col = fields.index('drying')
        keys = {key: key for key, _label in PANELS_DRYING_SELECTION}
        keys.update({label.split(' (')[0].lower(): key for key, label in PANELS_DRYING_SELECTION})
        keys.update({label: key for key, label in PANELS_DRYING_LABELS_AR.items()})
        keys['بدون'] = 'none'
        for row in data:
            value = row[col] if col < len(row) else ''
            # "KD (Kiln Dried)" / "KD (مجفف)" as exported: the code before the bracket.
            text = str(value or '').split(' (')[0].strip().lower()
            row[col] = keys.get(text, value) if text else 'none'
    for field_name, model_name in PANELS_IMPORT_VALUE_MODELS:
        if field_name not in fields:
            continue
        col = fields.index(field_name)
        Model = env[model_name]
        resolved = {}
        for row in data:
            value = row[col] if col < len(row) else ''
            if not isinstance(value, str) or not panels_clean_name(value):
                continue
            key = panels_clean_name(value).lower()
            if key not in resolved:
                resolved[key] = Model._panels_get_or_create(value).name
            row[col] = resolved[key]


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


# Dimension filter keys (thickness, width, "thickness x width"). They are
# selections so they can sit in the search panel (which does not take floats),
# with the values products actually have as options. Keys are zero-padded so
# grouping/sorting by the stored text follows the numeric order.
PANELS_DIMENSION_KEY_SEPARATOR = 'x'


def _panels_dimension_key(value):
    if not value or value <= 0:
        return False
    return '%015.4f' % value


def _panels_dimension_label(env, key):
    """'0000000018.0000x0000001220.0000' -> '18 × 1220'."""
    return ' × '.join(
        _panels_format_dimension_number(env, float(part))
        for part in key.split(PANELS_DIMENSION_KEY_SEPARATOR)
    )


def _panels_dimension_selection(model, field_name):
    """Selection options of a dimension filter field: the values in use."""
    env = model.env
    env['product.template'].flush_model([field_name])
    env.cr.execute(SQL(
        "SELECT DISTINCT %(f)s FROM product_template WHERE %(f)s IS NOT NULL ORDER BY 1",
        f=SQL.identifier(field_name),
    ))
    return [(key, _panels_dimension_label(env, key)) for (key,) in env.cr.fetchall()]


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

    # Keep the name parts canonical on product.template; expose on variant as editable related.
    kind_id = fields.Many2one(related='product_tmpl_id.kind_id', readonly=False)
    drying = fields.Selection(related='product_tmpl_id.drying', readonly=False)
    origin_id = fields.Many2one(related='product_tmpl_id.origin_id', readonly=False)
    mark_id = fields.Many2one(related='product_tmpl_id.mark_id', readonly=False)
    grade_id = fields.Many2one(related='product_tmpl_id.grade_id', readonly=False)
    subtype_id = fields.Many2one(related='product_tmpl_id.subtype_id', readonly=False)

    @api.onchange('kind_id', 'drying', 'origin_id', 'mark_id', 'grade_id', 'subtype_id', 'width', 'thickness')
    def _onchange_panels_auto_name(self):
        if len(self.product_tmpl_id.product_variant_ids) != 1:
            return
        name = self.env['product.template']._panels_build_product_name(
            self.kind_id.name, self.drying, self.origin_id.name, self.mark_id.name,
            self.grade_id.name, self.subtype_id.name, self.thickness, self.width,
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

    @api.model
    def load(self, fields, data):
        """Ensure auto-name after Excel imports on variants."""
        fields = list(fields or [])
        data = [list(row) for row in data or []]
        imported = _panels_import_base_fields(fields)
        if PANELS_AUTO_NAME_FIELDS & imported:
            _panels_prepare_import_rows(self.env, fields, data)
        res = super().load(fields, data)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if not (PANELS_AUTO_NAME_FIELDS & imported):
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
        string="Width",
        store=True,
        digits='Panels Millimeter',
        help="Product width - auto-fills in sale order line when product is selected."
    )

    thickness = fields.Float(
        string="Thickness",
        store=True,
        digits='Panels Millimeter',
        help="Product thickness - auto-fills in sale order line when product is selected."
    )

    # Canonical name parts (persist on template even with multiple variants).
    # Name: Type [KD/AD] Origin Sawmill Grade Sub-type ThicknessxWidth.
    kind_id = fields.Many2one(
        'panels.product.kind',
        string="Wood Type",
        ondelete='restrict',
        index=True,
        help="First part of the product name (e.g. Whitewood).",
    )

    drying = fields.Selection(
        PANELS_DRYING_SELECTION,
        string="Drying",
        default='none',
        help="KD (kiln dried) or AD (air dried); None = no drying, left out of the name.",
    )

    origin_id = fields.Many2one(
        'panels.product.origin',
        string="Origin",
        ondelete='restrict',
        index=True,
    )

    mark_id = fields.Many2one(
        'panels.product.mark',
        string="Sawmill",
        ondelete='restrict',
        index=True,
    )

    grade_id = fields.Many2one(
        'panels.product.grade',
        string="Grade",
        ondelete='restrict',
        index=True,
    )

    subtype_id = fields.Many2one(
        'panels.product.subtype',
        string="Sub-type",
        ondelete='restrict',
        index=True,
        help="Kept apart from the grade, e.g. Hasa Balta or OR for Fillery.",
    )

    # The wood type's rules (spec section 2), for the product form: which
    # parts it shows and which origins / grades it offers.
    panels_uses_drying = fields.Boolean(related='kind_id.uses_drying')
    panels_uses_origin = fields.Boolean(related='kind_id.uses_origin')
    panels_uses_grade = fields.Boolean(related='kind_id.uses_grade')
    panels_uses_subtype = fields.Boolean(related='kind_id.uses_subtype')
    panels_allowed_origin_ids = fields.Many2many(related='kind_id.origin_ids')
    panels_origin_has_grades = fields.Boolean(related='origin_id.has_grades')
    panels_allowed_grade_ids = fields.Many2many(related='origin_id.grade_ids')

    supplier_company_id = fields.Many2one(
        'res.partner',
        string="Supplier Company",
        domain=[('is_company', '=', True)],
        context={'default_is_company': True},
        help="The foreign company this product is imported from.",
    )

    # Filter-only copies of the dimensions (see _panels_dimension_selection).
    panels_thickness_filter = fields.Selection(
        selection=lambda self: _panels_dimension_selection(self, 'panels_thickness_filter'),
        string="Thickness (filter)",
        compute='_compute_panels_dimension_filters',
        store=True,
    )
    panels_width_filter = fields.Selection(
        selection=lambda self: _panels_dimension_selection(self, 'panels_width_filter'),
        string="Width (filter)",
        compute='_compute_panels_dimension_filters',
        store=True,
    )
    panels_dimensions = fields.Selection(
        selection=lambda self: _panels_dimension_selection(self, 'panels_dimensions'),
        string="Dimensions (Thickness × Width)",
        compute='_compute_panels_dimension_filters',
        store=True,
    )

    @api.depends('thickness', 'width')
    def _compute_panels_dimension_filters(self):
        for template in self:
            thickness = _panels_dimension_key(template.thickness)
            width = _panels_dimension_key(template.width)
            template.panels_thickness_filter = thickness
            template.panels_width_filter = width
            template.panels_dimensions = (
                thickness and width and PANELS_DIMENSION_KEY_SEPARATOR.join((thickness, width))
            )

    @api.model
    def get_import_templates(self):
        # Timber template first, in the user's language: its headers are the
        # field labels, so the import maps every column by itself; no name
        # column (it is built).
        suffix = '_ar' if (self.env.lang or '').startswith('ar') else ''
        return [{
            'label': _("Timber Products Import Template"),
            'template': f'/custom_sale_panels_multiplier/static/xls/product_template_timber{suffix}.xlsx',
        }] + super().get_import_templates()

    @api.model
    def _panels_build_product_name(self, kind, drying, origin, sawmill, grade, subtype,
                                   thickness, width, lang=None):
        """Build 'Whitewood KD Finland Norra V 22x100' (Arabic words
        in Arabic): empty parts are skipped, the size only shows when both
        thickness and width are set."""
        lang = lang or self.env.lang or 'en_US'
        drying_labels = PANELS_DRYING_LABELS_AR if lang.startswith('ar') else PANELS_DRYING_LABELS
        parts = [(kind or '').strip(), drying_labels.get(drying, '')]
        parts += [(value or '').strip() for value in (origin, sawmill, grade, subtype)]
        t = _panels_format_dimension_number(self.env, thickness)
        w = _panels_format_dimension_number(self.env, width)
        if t and w:
            parts.append(f'{t}x{w}')
        return ' '.join(part for part in parts if part)

    @api.model
    def _panels_name_from_vals(self, vals):
        """Product name from create/import values (ids or names)."""
        names = {}
        for field, model in PANELS_IMPORT_VALUE_MODELS:
            value = vals.get(field)
            names[field] = value if isinstance(value, str) else self.env[model].browse(value).name
        return self._panels_build_product_name(
            names['kind_id'], vals.get('drying'), names['origin_id'], names['mark_id'],
            names['grade_id'], names['subtype_id'], vals.get('thickness'), vals.get('width'),
        )

    def _panels_apply_auto_name(self):
        """Set the name in every installed language, each built from the
        values' names in that language (a write would only set the current one)."""
        self.ensure_one()
        langs = ['en_US'] + [code for code, _label in self.env['res.lang'].get_installed()
                             if code != 'en_US']
        names = {}
        for lang in langs:
            template = self.with_context(lang=lang)
            name = self._panels_build_product_name(
                template.kind_id.name, template.drying, template.origin_id.name,
                template.mark_id.name, template.grade_id.name, template.subtype_id.name,
                template.thickness, template.width, lang=lang,
            )
            if name:
                names[lang] = name
        if names:
            self.with_context(skip_panels_auto_name=True).update_field_translations('name', names)

    def _panels_spec_issues(self):
        """Name parts this product has but its wood type does not use."""
        self.ensure_one()
        kind, origin = self.kind_id, self.origin_id
        issues = []
        if not kind:
            return issues
        if self.drying and self.drying != 'none' and not kind.uses_drying:
            issues.append('drying')
        if origin and not kind.uses_origin:
            issues.append('origin_id')
        if self.grade_id and (not kind.uses_grade or (origin and not origin.has_grades)):
            issues.append('grade_id')
        if self.subtype_id and not (kind.uses_subtype and self.drying == 'ad'):
            issues.append('subtype_id')
        return issues

    @api.onchange('kind_id', 'drying', 'origin_id', 'mark_id', 'grade_id', 'subtype_id', 'width', 'thickness')
    def _onchange_panels_auto_name(self):
        # Clear the parts the chosen wood type / origin does not take, so the
        # name keeps to the spec (e.g. switching to Zaan drops origin and grade).
        for field in self._panels_spec_issues():
            self[field] = 'none' if field == 'drying' else False
        kind, origin = self.kind_id, self.origin_id
        if origin and kind.origin_ids and origin not in kind.origin_ids:
            self.origin_id = origin = False
        if self.grade_id and origin and origin.grade_ids and self.grade_id not in origin.grade_ids:
            self.grade_id = False
        name = self._panels_build_product_name(
            self.kind_id.name, self.drying, self.origin_id.name, self.mark_id.name,
            self.grade_id.name, self.subtype_id.name, self.thickness, self.width,
        )
        if name:
            self.name = name

    @api.constrains('type', 'kind_id', 'drying', 'origin_id', 'grade_id', 'subtype_id')
    def _check_panels_spec_rules(self):
        """Spec section 2: e.g. KD/AD only for Whitewood and Fillery, Zaan has
        no origin or grade, the sub-type replaces the grade on AD Fillery."""
        messages = {
            'drying': _("%(kind)s does not use KD/AD: choose None."),
            'origin_id': _("%(kind)s has no origin."),
            'grade_id': _("%(kind_origin)s has no grade."),
            'subtype_id': _("A sub-type is only used on AD products of a wood type with sub-types (Fillery)."),
        }
        for template in self.filtered(lambda t: t.type == 'consu'):
            issues = template._panels_spec_issues()
            if issues:
                raise ValidationError("\n".join(
                    messages[issue] % {
                        'kind': template.kind_id.name,
                        'kind_origin': ' '.join(filter(None, (template.kind_id.name, template.origin_id.name))),
                    }
                    for issue in issues
                ))

    @api.constrains('type', 'kind_id', 'drying', 'width', 'thickness')
    def _check_panels_dimensions_required(self):
        """Goods need a wood type, a drying choice (None is a valid choice) and
        both sizes. Origin, sawmill, grade and sub-type are optional: products
        without them skip that part of the name."""
        for template in self:
            if template.type != 'consu':
                continue
            missing = [
                label for value, label in (
                    (template.kind_id, _("Wood Type")),
                    (template.drying, _("Drying")),
                    (template.thickness, _("Thickness")),
                    (template.width, _("Width")),
                ) if not value
            ]
            if missing:
                raise ValidationError(_(
                    "Wood type, drying, thickness and width are required for goods so "
                    "every product name follows the same pattern. Missing: %s",
                    ', '.join(missing),
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                continue
            # The name field is readonly for goods: build the required name
            # here so a save never fails on it (form, API, quick create).
            name = self._panels_name_from_vals(dict(vals, drying=vals.get('drying', 'none')))
            if name:
                vals['name'] = name
            elif vals.get('type', 'consu') == 'consu':
                # Nothing to build a name from: use a placeholder so the save
                # reaches the check above and shows what is missing, instead
                # of a database error on the empty name.
                vals['name'] = '-'
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

    @api.model
    def load(self, fields, data):
        """Ensure auto-name during/after Excel imports on templates.

        Import of new products requires `name`. If the sheet omits `name` (or
        provides it blank), we auto-fill it from the timber fields
        before delegating to Odoo's import, then we also enforce auto-name after.
        """
        fields = list(fields or [])
        data = [list(row) for row in data or []]
        imported = _panels_import_base_fields(fields)

        if PANELS_AUTO_NAME_FIELDS & imported:
            _panels_prepare_import_rows(self.env, fields, data)

            # Pre-fill required `name` for create imports when it is missing/blank.
            name_idx = fields.index('name') if 'name' in fields else None
            if name_idx is None:
                fields.append('name')
                name_idx = len(fields) - 1
                data = [list(row) + [''] for row in data]

            idx = {f: fields.index(f) for f in PANELS_AUTO_NAME_FIELDS if f in fields}

            for row in data:
                current = row[name_idx] if name_idx < len(row) else ''
                if isinstance(current, str) and current.strip():
                    continue
                if current not in (False, None, ''):
                    continue
                vals = {f: row[i] for f, i in idx.items()}
                row[name_idx] = self._panels_name_from_vals(vals) or 'Imported Product'

        res = super().load(fields, data)
        if self.env.context.get('skip_panels_auto_name'):
            return res
        if not (PANELS_AUTO_NAME_FIELDS & imported):
            return res
        ids = _panels_load_result_ids(res)
        if not ids:
            return res
        templates = self.browse(ids).exists()
        for tmpl in templates:
            tmpl.with_context(skip_panels_auto_name=True)._panels_apply_auto_name()
        return res
