# -*- coding: utf-8 -*-
# Timber name parts as reusable lists (wood type, origin, sawmill, grade,
# sub-type): the user picks a saved value in the product form, or types a new
# one and creates it inline.

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.sql import escape_psql


def panels_clean_name(name):
    """Trim and collapse inner spaces so ' Pine  A ' and 'Pine A' are one value."""
    return ' '.join((name or '').split())


class PanelsNamedValueMixin(models.AbstractModel):
    _name = 'panels.named.value.mixin'
    _description = 'Panels Mark / Grade value'

    # Field on product.template that points at the concrete model.
    _panels_product_field = None

    name = fields.Char(string="الاسم", required=True)
    active = fields.Boolean(string="نشط", default=True)
    product_count = fields.Integer(string="عدد المنتجات", compute='_compute_product_count')

    def _compute_product_count(self):
        field = self._panels_product_field
        groups = self.env['product.template'].with_context(active_test=False)._read_group(
            [(field, 'in', self.ids)], [field], ['__count'],
        )
        counts = {value.id: count for value, count in groups}
        for record in self:
            record.product_count = counts.get(record.id, 0)

    @api.constrains('name')
    def _check_name_not_empty(self):
        for record in self:
            if not panels_clean_name(record.name):
                raise ValidationError("الاسم مطلوب.")

    @api.model
    def _panels_find_by_name(self, name):
        """Case/space-insensitive lookup, archived values included."""
        clean = panels_clean_name(name)
        if not clean:
            return self.browse()
        return self.with_context(active_test=False).search(
            [('name', '=ilike', escape_psql(clean))], limit=1,
        )

    @api.model
    def _panels_get_or_create(self, name):
        """Return the saved value matching `name` (unarchived), creating it if new."""
        record = self._panels_find_by_name(name)
        if record:
            if not record.active:
                record.active = True
            return record
        return self.create({'name': name})

    @api.model
    def _panels_seed(self, names):
        """Add the standard values from the client's spec, skipping any that
        already exist (archived ones stay archived)."""
        for name in names:
            if not self._panels_find_by_name(name):
                self.create({'name': name})

    @api.model
    def name_create(self, name):
        # "Create" from the dropdown reuses an existing value typed with
        # different case/spacing instead of failing on the unique index.
        if panels_clean_name(name):
            record = self._panels_get_or_create(name)
            return record.id, record.display_name
        return super().name_create(name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                vals['name'] = panels_clean_name(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals = dict(vals, name=panels_clean_name(vals['name']))
        res = super().write(vals)
        if 'name' in vals:
            # Product names embed this value: rebuild them after a rename.
            templates = self.env['product.template'].with_context(active_test=False).search(
                [(self._panels_product_field, 'in', self.ids)]
            )
            for template in templates:
                template._panels_apply_auto_name()
        return res


class PanelsProductMark(models.Model):
    _name = 'panels.product.mark'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Sawmill'
    _order = 'name'

    _panels_product_field = 'mark_id'

    _name_uniq = models.UniqueIndex(
        '(lower(name))',
        "هذا المنشار موجود بالفعل.",
    )

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed([
            'Adelina', 'Anaika Wood', 'Andrewex', 'Astar', 'Balungstrads',
            'Beliy Ruchey', 'Bergene Hollmas', 'Binderholz', 'Canadian', 'Ersaha',
            'Fiskarheden', 'FM Timber', 'HAL', 'Hanasa', 'Hasa', 'Hedlunds', 'HJN',
            'Holmen', 'Ingarp', 'IPO Wood', 'ISOJOEN', 'JPJ-WOOD', 'Junnikkala',
            'Jutos', 'Kaivospuu', 'Karl Segerstrom', 'Keitele Timber K.T.S',
            'Koskasine', 'LE', 'Luvia', 'Luze', 'Metsa', 'Moelven', 'NK Lundstorms',
            'Nordana', 'Norra Timber', 'Orasko', 'Rodins', 'RWA', 'Sahakuto',
            'Sandasa', 'SCA', 'Segezha', 'Setra Group', 'Sodra', 'Stenvalls',
            'Stora Enso', 'UPM Timber', 'VersoWood', 'Viitala Forest', 'VLP',
            'Wallans', 'Westas',
        ])


class PanelsProductGrade(models.Model):
    _name = 'panels.product.grade'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Grade'
    _order = 'name'

    _panels_product_field = 'grade_id'

    _name_uniq = models.UniqueIndex(
        '(lower(name))',
        "هذه الدرجة موجودة بالفعل.",
    )

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed([
            'O/S', 'V', 'VI', 'SF', 'VI DOM', 'Reject', 'Shaal EXP',
            'Shaal EXP Blue', 'Shaal Mix', 'Shaal DOM', 'IV', 'DOM',
        ])


class PanelsProductKind(models.Model):
    """Wood type (Whitewood, Redwood...): first part of the product name. The
    abbreviation is how suppliers write it (e.g. "RW 25x100 Schaal KD")."""
    _name = 'panels.product.kind'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Wood Type'
    _order = 'name'

    _panels_product_field = 'kind_id'

    code = fields.Char(string="الاختصار")

    _name_uniq = models.UniqueIndex(
        '(lower(name))',
        "نوع الخشب هذا موجود بالفعل.",
    )
    _code_uniq = models.UniqueIndex(
        '(lower(code)) WHERE code IS NOT NULL',
        "هذا الاختصار مستخدم لنوع خشب آخر.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = panels_clean_name(vals['code']).upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals = dict(vals, code=panels_clean_name(vals['code']).upper())
        return super().write(vals)

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed(['Whitewood', 'Redwood', 'Zaan', 'Fillery'])
        for name, code in (('Whitewood', 'WW'), ('Redwood', 'RW')):
            kind = self._panels_find_by_name(name)
            if kind and not kind.code and not self.with_context(active_test=False).search_count(
                    [('code', '=ilike', code)]):
                kind.code = code


class PanelsProductOrigin(models.Model):
    _name = 'panels.product.origin'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Origin'
    _order = 'name'

    _panels_product_field = 'origin_id'

    _name_uniq = models.UniqueIndex(
        '(lower(name))',
        "هذا المنشأ موجود بالفعل.",
    )

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed([
            'Finland', 'Russia', 'Germany', 'Romania', 'Canada', 'Sweden',
            'Latvia', 'Estonia',
        ])


class PanelsProductSubtype(models.Model):
    """Sub-type kept apart from the grade (e.g. Fillery AD: Hasa Balta, OR)."""
    _name = 'panels.product.subtype'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Sub-type'
    _order = 'name'

    _panels_product_field = 'subtype_id'

    _name_uniq = models.UniqueIndex(
        '(lower(name))',
        "هذا النوع موجود بالفعل.",
    )

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed(['Hasa Balta', 'Hasa Manshour', 'OR', 'AW', 'Canadian'])
