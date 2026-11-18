# -*- coding: utf-8 -*-

from . import models
from .models.panels_mark_grade import panels_apply_spec_rules


def post_init_hook(env):
    # Fresh install: the seeded wood types / origins get the spec rules.
    panels_apply_spec_rules(env)
