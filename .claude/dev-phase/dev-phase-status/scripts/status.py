'''dev-phase-status — token-efficient status report for the active plan.

Reads PLAN.md + PROGRESS.md + git + CHANGELOG [Unreleased] and prints a compact summary.
Read-only; never mutates. Use --json for a machine-readable payload.

    $VENV/python .claude/skills/dev-phase-status/scripts/status.py [--json]
'''

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# skill scripts live at .claude/skills/<skill>/scripts/ -> parents[2] is the shared skills/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402


def build_report() -> dict:
    root, cfg = tl.load()
    plan_text = tl.read(tl.path_for(root, cfg, 'plan'))
    version = tl.read_version(root, cfg)
    changelog = tl.read(tl.path_for(root, cfg, 'changelog'))
    unreleased = tl.changelog_unreleased(changelog)
    porcelain = tl.git_porcelain(root)

    branch = tl.git_branch(root)
    release_branch = cfg.get('release_branch', 'main')
    ab = tl.git_ahead_behind(root, release_branch)  # None when on/unknown base

    report = {
        'version': version,
        'branch': branch,
        'release_branch': release_branch,
        'ahead': ab[0] if ab else None,
        'behind': ab[1] if ab else None,
        # unmerged plan work sitting off the release branch — the drift this whole policy guards
        'branch_drift': bool(ab and branch != release_branch and ab[0] > 0),
        'uncommitted': len(porcelain),
        'uncommitted_sample': porcelain[:10],
        'unreleased_bullets': len(unreleased),
        'unreleased_sample': unreleased[:10],
        'plan_active': False,
    }

    if plan_text and not tl.plan_is_stub(plan_text):
        plan = tl.parse_plan(plan_text)
        rows = plan['rows']
        cursor = tl.plan_cursor(rows)
        ready = tl.plan_ready(rows)
        report.update({
            'plan_active': True,
            'plan_meta': plan['meta'],
            'phases': [
                {'phase': r['phase'], 'items': r['items'], 'depends': r['depends'],
                 'release': r['release'], 'version': r['version'], 'status': r['status']}
                for r in rows
            ],
            'counts': {
                'done': sum(1 for r in rows if r['status'] in ('done', 'released')),
                'in_progress': sum(1 for r in rows if r['status'] == 'in-progress'),
                'pending': sum(1 for r in rows if r['status'] == 'pending'),
                'total': len(rows),
            },
            'cursor': cursor['phase'] if cursor else None,
            'ready': [r['phase'] for r in ready],
            'parallelizable': [r['phase'] for r in ready] if len(ready) > 1 else [],
        })
    return report


def render_text(r: dict) -> str:
    out = [f"version: {r['version']}   branch: {r['branch']}"]
    if r['branch'] != r.get('release_branch') and r.get('ahead') is not None:
        drift = ' — UNMERGED' if r.get('branch_drift') else ''
        out.append(f"vs {r['release_branch']}: {r['ahead']} ahead, {r['behind']} behind{drift}")
    if not r['plan_active']:
        out.append('plan: none active')
    else:
        c = r['counts']
        out.append(f"plan: {c['done']}/{c['total']} done, {c['in_progress']} in-progress, "
                   f"{c['pending']} pending   cadence: {r['plan_meta'].get('cadence', '?')}")
        for p in r['phases']:
            out.append(f"  {p['phase']:<6} [{p['status']:<11}] {p['release']:<4} "
                       f"{p['items'] or '—':<14} deps:{p['depends']} ver:{p['version']}")
        if r['cursor']:
            out.append(f"cursor: {r['cursor']}")
        if r['parallelizable']:
            out.append(f"parallelizable now: {', '.join(r['parallelizable'])} "
                       f"(independent — run in separate sessions)")
        elif r['ready']:
            out.append(f"ready next: {', '.join(r['ready'])}")
    out.append(f"uncommitted: {r['uncommitted']} file(s)")
    out.append(f"CHANGELOG [Unreleased]: {r['unreleased_bullets']} bullet(s)")
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description='Active-plan status report.')
    ap.add_argument('--json', action='store_true', help='emit JSON')
    args = ap.parse_args()
    report = build_report()
    print(json.dumps(report, indent=2) if args.json else render_text(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
