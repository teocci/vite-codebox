'''Shared test setup for the repo's Python scripts.

Puts ``scripts/py/`` on ``sys.path`` so tests import the modules directly,
without installing a package — the same arrangement codeblox-builder and the
dev-phase family use.
'''

import sys
from pathlib import Path

_SCRIPTS_PY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_PY))
