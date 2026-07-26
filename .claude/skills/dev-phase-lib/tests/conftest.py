'''Shared test setup for the dev-phase family.

The suite spans the whole family, so it is hosted in ``dev-phase-lib`` — the family's
shared-code home — and reaches sideways to its siblings. Adds each skill's ``scripts/``
dir to ``sys.path`` so tests import the modules directly (``tracklib``, ``order``,
``check_coherence``) without installing a package.
'''

import sys
from pathlib import Path

# tests live at <container>/dev-phase-lib/tests/ -> parents[2] is the container of the
# sibling skill dirs: skills/ in the source repo, .claude/skills/ once deployed.
_SKILLS_ROOT = Path(__file__).resolve().parents[2]
_SKILL_NAMES = (
    'dev-phase-lib',
    'dev-phase-workflow',
    'dev-phase-status',
    'dev-phase-complete',
    'dev-phase-start',
)
for _skill in _SKILL_NAMES:
    _scripts = _SKILLS_ROOT / _skill / 'scripts'
    if _scripts.is_dir():
        sys.path.insert(0, str(_scripts))
