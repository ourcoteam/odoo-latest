# -*- coding: utf-8 -*-
# Timber name parts as reusable lists (wood type, origin, sawmill, grade,
# sub-type): the user picks a saved value in the product form, or types a new
# one and creates it inline.

from odoo import _, api, fields, models
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

    # Translatable: Arabic users see Arabic values (e.g. Whitewood in Arabic) and the
    # product name is built in each language from them.
    name = fields.Char(string="Name", required=True, translate=True)
    active = fields.Boolean(string="Active", default=True)
    product_count = fields.Integer(string="Products", compute='_compute_product_count')

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
                raise ValidationError(_("The name is required."))

    @api.model
    def _panels_find_by_name(self, name):
        """Case/space-insensitive lookup in English and in the user's language
        (a sheet may say the English or the Arabic name), archived values included."""
        clean = panels_clean_name(name)
        if not clean:
            return self.browse()
        for lang in dict.fromkeys(('en_US', self.env.lang or 'en_US')):
            record = self.with_context(active_test=False, lang=lang).search(
                [('name', '=ilike', escape_psql(clean))], limit=1,
            )
            if record:
                return record.with_context(lang=self.env.lang)
        return self.browse()

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
    def _panels_seed(self, names, arabic=None):
        """Add the standard values from the client's spec, skipping any that
        already exist (archived ones stay archived). `arabic` maps an English
        name to its Arabic name, set only while the Arabic one is untouched."""
        arabic = arabic or {}
        ar_langs = [code for code, _label in self.env['res.lang'].get_installed()
                    if code.startswith('ar')]
        for name in names:
            record = self.with_context(lang='en_US')._panels_find_by_name(name)
            if not record:
                record = self.with_context(lang='en_US').create({'name': name})
            if name in arabic and ar_langs:
                english = record.with_context(lang='en_US').name
                langs = [lang for lang in ar_langs
                         if record.with_context(lang=lang).name == english]
                if langs:
                    record.update_field_translations('name', dict.fromkeys(langs, arabic[name]))

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
        "(lower(name->>'en_US'))",
        "This sawmill already exists.",
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
        "(lower(name->>'en_US'))",
        "This grade already exists.",
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

    code = fields.Char(string="Abbreviation")

    # Which parts of the product name this wood type has (spec section 2):
    # the product form only shows those, and saving checks them.
    uses_drying = fields.Boolean(string="Uses KD/AD", default=True)
    uses_origin = fields.Boolean(string="Uses Origin", default=True)
    uses_grade = fields.Boolean(string="Uses Grade", default=True)
    uses_subtype = fields.Boolean(
        string="Uses Sub-type", default=False,
        help="AD products of this wood type take a sub-type instead of a grade (Fillery).",
    )
    origin_ids = fields.Many2many(
        'panels.product.origin', string="Origins",
        help="Origins offered for this wood type. Empty = all.",
    )

    _name_uniq = models.UniqueIndex(
        "(lower(name->>'en_US'))",
        "This wood type already exists.",
    )
    _code_uniq = models.UniqueIndex(
        '(lower(code)) WHERE code IS NOT NULL',
        "This abbreviation is already used by another wood type.",
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
        self._panels_seed(['Whitewood', 'Redwood', 'Zaan', 'Fillery'], arabic={
            'Whitewood': 'بياض', 'Redwood': 'سويد', 'Zaan': 'زان', 'Fillery': 'فلليري',
        })
        for name, code in (('Whitewood', 'WW'), ('Redwood', 'RW')):
            kind = self.with_context(lang='en_US')._panels_find_by_name(name)
            if kind and not kind.code and not self.with_context(active_test=False).search_count(
                    [('code', '=ilike', code)]):
                kind.code = code


class PanelsProductOrigin(models.Model):
    _name = 'panels.product.origin'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Origin'
    _order = 'name'

    _panels_product_field = 'origin_id'

    has_grades = fields.Boolean(string="Has Grades", default=True)
    grade_ids = fields.Many2many(
        'panels.product.grade', string="Grades",
        help="Grades offered for this origin. Empty = all.",
    )

    _name_uniq = models.UniqueIndex(
        "(lower(name->>'en_US'))",
        "This origin already exists.",
    )

    @api.model
    def _panels_seed_defaults(self):
        arabic = {
            'Finland': 'فنلندا', 'Russia': 'روسيا', 'Germany': 'ألمانيا',
            'Romania': 'رومانيا', 'Canada': 'كندا', 'Sweden': 'السويد',
            'Latvia': 'لاتفيا', 'Estonia': 'إستونيا',
        }
        self._panels_seed(list(arabic), arabic=arabic)


class PanelsProductSubtype(models.Model):
    """Sub-type kept apart from the grade (e.g. Fillery AD: Hasa Balta, OR)."""
    _name = 'panels.product.subtype'
    _inherit = 'panels.named.value.mixin'
    _description = 'Panels Sub-type'
    _order = 'name'

    _panels_product_field = 'subtype_id'

    _name_uniq = models.UniqueIndex(
        "(lower(name->>'en_US'))",
        "This sub-type already exists.",
    )

    @api.model
    def _panels_seed_defaults(self):
        self._panels_seed(['Hasa Balta', 'Hasa Manshour', 'OR', 'AW', 'Canadian'])


# Spec section 2 (Odoo Requirements OAG): parts of the name per wood type,
# origins per wood type and grades per origin. Applied once (install /
# 19.0.1.0.20 upgrade); afterwards they are edited from the configuration lists.
PANELS_SPEC_KINDS = {
    'Whitewood': {'uses_drying': True, 'uses_origin': True, 'uses_grade': True, 'uses_subtype': False,
                  'origins': ['Finland', 'Russia', 'Germany', 'Romania']},
    'Redwood': {'uses_drying': False, 'uses_origin': True, 'uses_grade': True, 'uses_subtype': False,
                'origins': ['Finland', 'Russia']},
    'Zaan': {'uses_drying': False, 'uses_origin': False, 'uses_grade': False, 'uses_subtype': False,
             'origins': []},
    'Fillery': {'uses_drying': True, 'uses_origin': True, 'uses_grade': False, 'uses_subtype': True,
                'origins': ['Canada', 'Finland', 'Russia', 'Sweden', 'Latvia', 'Estonia']},
}
PANELS_SPEC_ORIGIN_GRADES = {
    'Finland': ['O/S', 'V', 'VI', 'SF', 'VI DOM', 'Reject', 'Shaal EXP', 'Shaal EXP Blue',
                'Shaal Mix', 'Shaal DOM'],
    'Russia': ['IV', 'V', 'DOM'],
    'Germany': None,  # no grades
    'Romania': None,
}


def panels_apply_spec_rules(env):
    """Set the spec rules on the standard wood types and origins."""
    env = env(context=dict(env.context, lang='en_US', active_test=False))
    Origin, Grade = env['panels.product.origin'], env['panels.product.grade']
    for name, rules in PANELS_SPEC_KINDS.items():
        kind = env['panels.product.kind']._panels_find_by_name(name)
        if not kind:
            continue
        origins = Origin.browse([Origin._panels_find_by_name(o).id for o in rules['origins']]).exists()
        kind.write(dict(
            {key: value for key, value in rules.items() if key != 'origins'},
            origin_ids=[(6, 0, origins.ids)],
        ))
    for name, grades in PANELS_SPEC_ORIGIN_GRADES.items():
        origin = Origin._panels_find_by_name(name)
        if not origin:
            continue
        if grades is None:
            origin.write({'has_grades': False, 'grade_ids': [(5,)]})
        else:
            found = Grade.browse([Grade._panels_find_by_name(g).id for g in grades]).exists()
            origin.write({'has_grades': True, 'grade_ids': [(6, 0, found.ids)]})
