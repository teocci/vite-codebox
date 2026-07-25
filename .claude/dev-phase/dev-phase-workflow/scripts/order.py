'''dev-phase-workflow — execution sequencing over the plan dependency DAG.

Two modes:
  --suggest (default): full execution order as dependency waves (a wave with >1 phase can run
                       in parallel sessions). Use in plan mode to propose an order.
  --next             : the phases ready to start right now (deps all done, not yet done).

    $VENV/python .claude/skills/dev-phase-workflow/scripts/order.py [--suggest|--next] [--json]
'''

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# skill scripts live at .claude/skills/<skill>/scripts/ -> parents[2] is the shared skills/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402


def compute_waves(rows: list[dict]) -> tuple[list[list[str]], dict]:
    '''Kahn-by-levels over not-yet-released phases; done phases are satisfied prereqs.'''
    done = {r['phase'] for r in rows if r['status'] in ('done', 'released')}
    all_phases = {r['phase'] for r in rows}
    remaining = {r['phase']: set(r['depends_list']) for r in rows
                 if r['status'] not in ('done', 'released')}
    unknown = {p: sorted(deps - all_phases) for p, deps in remaining.items()
               if deps - all_phases - done}

    waves: list[list[str]] = []
    satisfied = set(done)
    while remaining:
        wave = sorted(p for p, deps in remaining.items() if deps <= satisfied)
        if not wave:
            blocked = {p: sorted(deps - satisfied) for p, deps in remaining.items()}
            return waves, {'blocked': blocked, 'unknown': unknown}
        waves.append(wave)
        for p in wave:
            del remaining[p]
        satisfied |= set(wave)
    return waves, {'blocked': {}, 'unknown': unknown}


def build() -> dict:
    root, cfg = tl.load()
    plan_text = tl.read(tl.path_for(root, cfg, 'plan'))
    if not plan_text or tl.plan_is_stub(plan_text):
        return {'plan_active': False}
    rows = tl.parse_plan(plan_text)['rows']
    waves, diag = compute_waves(rows)
    ready = [r['phase'] for r in tl.plan_ready(rows)]
    return {
        'plan_active': True,
        'waves': waves,
        'ready': ready,
        'parallelizable': ready if len(ready) > 1 else [],
        'blocked': diag['blocked'],
        'unknown_deps': diag['unknown'],
    }


def render(data: dict, mode: str) -> str:
    if not data['plan_active']:
        return 'plan: none active'
    out = []
    if mode == 'next':
        if data['ready']:
            out.append('ready now: ' + ', '.join(data['ready']))
            if data['parallelizable']:
                out.append('→ independent; run each in a separate session')
        else:
            out.append('nothing ready (all done, or blocked)')
    else:
        out.append('execution order (waves):')
        for i, wave in enumerate(data['waves'], 1):
            tag = '  (parallel)' if len(wave) > 1 else ''
            out.append(f'  wave {i}: {", ".join(wave)}{tag}')
        if not data['waves']:
            out.append('  (nothing left to run)')
    if data['blocked']:
        out.append('blocked: ' + '; '.join(f'{p} needs {d}' for p, d in data['blocked'].items()))
    if data['unknown_deps']:
        out.append('unknown deps: ' + '; '.join(f'{p}→{d}' for p, d in data['unknown_deps'].items()))
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description='Dependency-aware phase sequencing.')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--suggest', action='store_true', help='full order as waves (default)')
    g.add_argument('--next', action='store_true', help='phases ready to start now')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    data = build()
    mode = 'next' if args.next else 'suggest'
    print(json.dumps(data, indent=2) if args.json else render(data, mode))
    # non-zero when a cycle/blockage leaves work unschedulable
    return 1 if data.get('blocked') else 0


if __name__ == '__main__':
    raise SystemExit(main())
