'''dev-phase-complete Part A — mark a phase done (mechanical cross-file bookkeeping).

Flips the phase's status to `done` in PLAN.md and PROGRESS.md. The model separately fills the
detail-file bodies and appends the CHANGELOG [Unreleased] bullets (prose). Version stamping and
index done-markers happen at release time (cut_release.py), because the version is only known then.

    $VENV/python .claude/skills/dev-phase-complete/scripts/finalize_phase.py P-16 [--dry-run]
'''

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# skill scripts live at .claude/skills/<skill>/scripts/ -> parents[2] is the shared skills/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402


def pnum(x: str) -> str:
    m = re.search(r'(\d+)', x)
    return m.group(1) if m else x


def pid(x: str) -> str:
    n = pnum(x)
    return f'P-{n}' if n.isdigit() else x


def finalize(phase: str, dry_run: bool) -> dict:
    root, cfg = tl.load()
    target_pid, target_num = pid(phase), pnum(phase)

    plan_p = tl.path_for(root, cfg, 'plan')
    prog_p = tl.path_for(root, cfg, 'progress')
    plan_text = tl.read(plan_p)
    prog_text = tl.read(prog_p)

    new_plan = tl.update_table_rows(
        plan_text, ('Phase', 'Items', 'Status'),
        key_pred=lambda c: c and c[0] == target_pid,
        transform=lambda c: c[:-1] + ['done'],
    )
    new_prog = tl.update_table_rows(
        prog_text, ('Phase', 'Title', 'Status'),
        key_pred=lambda c: c and c[0] == target_num,
        transform=lambda c: c[:-1] + ['done'],
    )

    changed_plan = new_plan != plan_text
    changed_prog = new_prog != prog_text
    if not dry_run:
        if changed_plan:
            tl.write(plan_p, new_plan)
        if changed_prog:
            tl.write(prog_p, new_prog)

    return {
        'phase': target_pid,
        'plan_updated': changed_plan,
        'progress_updated': changed_prog,
        'dry_run': dry_run,
        'note': 'model: fill detail bodies + append CHANGELOG [Unreleased] bullets; '
                'run cut_release.py when this phase closes its release group.',
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Mark a phase done (Part A).')
    ap.add_argument('phase', help='phase id, e.g. P-16 or 16')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    import json
    print(json.dumps(finalize(args.phase, args.dry_run), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
