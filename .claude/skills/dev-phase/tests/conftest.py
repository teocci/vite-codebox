'''Shared test setup for the dev-phase family.

Adds each skill's ``scripts/`` dir to ``sys.path`` so tests import the modules
directly (``tracklib``, ``order``, ``check_coherence``) without installing a package.
'''

import sys
from pathlib import Path

_FAMILY = Path(__file__).resolve().parents[1]  # skills/dev-phase/
_SKILLS = (
    'dev-phase-lib',
    'dev-phase-workflow',
    'dev-phase-status',
    'dev-phase-complete',
    'dev-phase-start',
)
for _skill in _SKILLS:
    _scripts = _FAMILY / _skill / 'scripts'
    if _scripts.is_dir():
        sys.path.insert(0, str(_scripts))
