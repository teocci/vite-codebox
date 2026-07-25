'''dev-phase-start — scaffold tracking structure for an approved plan.

Reads a plan spec (JSON, via --spec FILE or stdin), allocates the next-free phase/item ids,
creates detail stubs, inserts in-progress index rows, adds planned PROGRESS rows, and writes
PLAN.md. Docs-only: never bumps the version, edits CHANGELOG, or runs git.

Spec shape:
  {
    "approved": "2026-07-17", "branch": "feat/x", "cadence": "per-phase",
    "phases": [
      {"title": "Command-scoped flags", "depends": [], "release": "R1",
       "items": [{"kind": "improvement", "title": "...", "summary": "one-line",
                  "objective": "...", "related": "siblings I-6"}]}
    ]
  }
"depends" entries are 0-based indices into this spec's "phases" array.

    $VENV/python .claude/skills/dev-phase-start/scripts/scaffold.py --spec plan.json [--dry-run]
'''

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# skill scripts live at .claude/skills/<skill>/scripts/ -> parents[2] is the shared skills/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402


def _max_id(text: str, prefix: str) -> int:
    nums = [int(n) for n in re.findall(prefix + r'-(\d+)', text)]
    return max(nums) if nums else 0


def _max_phase_num(progress: str) -> int:
    # phase table ids are bare integers (non-numeric like 'Auth' ignored)
    nums = []
    for cells in tl._iter_table_rows(progress, ('Phase', 'Title', 'Status')):
        if cells and cells[0].isdigit():
            nums.append(int(cells[0]))
    return max(nums) if nums else -1


def phase_stub(pnum: int, title: str, objective: str) -> str:
    return (f'# Phase {pnum} — {title}\n\n'
            f'- **Phase ID:** {pnum}\n- **Version:** (pending)\n- **Date:** (pending)\n'
            f'- **Tests:** (pending)\n- **Status:** 🚧 IN PROGRESS\n\n'
            f'## Objective\n\n{objective or "(from the approved plan)"}\n\n'
            f'## What was built\n\n(fill during work)\n\n'
            f'## Files changed\n\n| File | Change |\n|---|---|\n\n'
            f'## Verification\n\n(fill during work)\n')


def item_stub(kind: str, iid: str, title: str, summary: str, objective: str, related: str) -> str:
    if kind == 'fix':
        return (f'# {iid} — {title}\n\n'
                f'- **Fix ID:** {iid}\n- **Version:** (pending)\n- **Date:** (pending)\n'
                f'- **Status:** 🚧 IN PROGRESS\n- **Related work:** {related or "(tbd)"}\n\n'
                f'## Symptom\n\n{summary or "(describe the bug)"}\n\n'
                f'## Root cause\n\n(fill during work)\n\n## Fix\n\n(fill during work)\n\n'
                f'## Files changed\n\n| File | Change |\n|---|---|\n\n'
                f'## Verification\n\n(fill during work)\n')
    return (f'# {iid} — {title}\n\n'
            f'- **Improvement ID:** {iid}\n- **Version:** (pending)\n- **Date:** (pending)\n'
            f'- **Status:** 🚧 IN PROGRESS\n- **Related work:** {related or "(tbd)"}\n\n'
            f'## Objective\n\n{objective or summary or "(from the approved plan)"}\n\n'
            f'## Approach\n\n(fill during work)\n\n'
            f'## Files changed\n\n| File | Change |\n|---|---|\n\n'
            f'## Verification\n\n(fill during work)\n')


def build_plan_md(meta: dict, rows: list[dict]) -> str:
    head = (f"# Active Plan\n\n"
            f"**Approved:** {meta.get('approved', '(tbd)')}  "
            f"**Branch:** {meta.get('branch', '(tbd)')}  "
            f"**Cadence:** {meta.get('cadence', 'per-phase')}\n\n")
    tbl = ['| Phase | Items | Depends | Release | Version | Status |',
           '|-------|-------|---------|---------|---------|--------|']
    for r in rows:
        tbl.append(f"| {r['phase']} | {r['items']} | {r['depends']} | {r['release']} "
                   f"| (pending) | pending |")
    return head + '\n'.join(tbl) + '\n'


def _branch_guard(root: Path, cfg: dict) -> str | None:
    '''Refuse-message if scaffolding on the release branch under integration=branch, else None.

    Read-only (never creates a branch — that's a runbook step). See conventions §7b guard 1.
    '''
    if cfg.get('integration') != 'branch':
        return None
    rb = cfg.get('release_branch', 'main')
    cur = tl.git_branch(root)
    if cur and cur == rb:
        return (f"on release branch '{rb}' with integration=branch — refuse to scaffold a plan here. "
                f"Create the plan branch first (git switch -c feat/<slug>, or a worktree for a "
                f"parallel session), then re-run scaffold.")
    return None


def scaffold(spec: dict, dry_run: bool) -> dict:
    root, cfg = tl.load()
    guard = _branch_guard(root, cfg)
    if guard and not dry_run:
        print(json.dumps({'error': guard, 'branch': tl.git_branch(root)}), file=sys.stderr)
        raise SystemExit(2)
    P = lambda k: tl.path_for(root, cfg, k)  # noqa: E731

    progress = tl.read(P('progress'))
    improvements = tl.read(P('improvements'))
    fixes = tl.read(P('fixes'))

    next_phase = _max_phase_num(progress) + 1
    next_i = _max_id(improvements, 'I') + 1
    next_f = _max_id(fixes, 'F') + 1

    planned = []          # phase ids for spec-index → 'P-N'
    plan_rows = []
    files: dict[str, str] = {}
    imp_rows, fix_rows, prog_rows = [], [], []

    for idx, ph in enumerate(spec['phases']):
        pnum = next_phase + idx
        pid = f'P-{pnum}'
        planned.append(pid)
        item_ids = []
        for it in ph.get('items', []):
            if it['kind'] == 'fix':
                iid = f'F-{next_f}'; next_f += 1
                files[str(P('fixes_dir') / f'{iid}.md')] = item_stub(
                    'fix', iid, it['title'], it.get('summary', ''), '', it.get('related', ''))
                fix_rows.append(f"| [{iid}](fixes/{iid}.md) | {it.get('summary', '(tbd)')} "
                                f"| (tbd) | (tbd) |  |")
            else:
                iid = f'I-{next_i}'; next_i += 1
                files[str(P('improvements_dir') / f'{iid}.md')] = item_stub(
                    'improvement', iid, it['title'], it.get('summary', ''),
                    it.get('objective', ''), it.get('related', ''))
                imp_rows.append(f"| [{iid}](improvements/{iid}.md) | {it.get('summary', '(tbd)')} "
                                f"| 🚧 In progress. |")
            item_ids.append(iid)

        files[str(P('phases_dir') / f'phase-{pnum}.md')] = phase_stub(
            pnum, ph['title'], ph.get('objective', ''))
        prog_rows.append(f"| {pnum} | {ph['title']} | planned |")
        plan_rows.append({
            'phase': pid,
            'items': ', '.join(item_ids) if item_ids else '—',
            'depends': ', '.join(planned[d] for d in ph.get('depends', [])) or '—',
            'release': ph.get('release', f'R{idx + 1}'),
        })

    meta = {k: spec.get(k) for k in ('approved', 'branch', 'cadence')}
    meta['branch'] = meta.get('branch') or tl.git_branch(root)
    plan_md = build_plan_md(meta, plan_rows)

    # apply
    edits = {}
    if imp_rows:
        edits[str(P('improvements'))] = tl.append_table_rows(improvements, ('ID', 'Idea', 'Notes'), imp_rows)
    if fix_rows:
        edits[str(P('fixes'))] = tl.append_table_rows(fixes, ('ID', 'Symptom', 'Fix'), fix_rows)
    edits[str(P('progress'))] = tl.append_table_rows(progress, ('Phase', 'Title', 'Status'), prog_rows)
    edits[str(P('plan'))] = plan_md
    edits.update(files)

    if not dry_run:
        for path, content in edits.items():
            tl.write(Path(path), content)

    result = {
        'phases': planned,
        'improvements': [r for r in imp_rows],
        'fixes': [r for r in fix_rows],
        'files_created': list(files),
        'files_edited': [str(P(k)) for k in ('improvements', 'fixes', 'progress', 'plan')
                         if str(P(k)) in edits],
        'dry_run': dry_run,
    }
    if guard:  # dry-run only reaches here; surface the branch warning without blocking the preview
        result['warning'] = guard
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description='Scaffold an approved plan.')
    ap.add_argument('--spec', type=Path, help='plan spec JSON (default: stdin)')
    ap.add_argument('--dry-run', action='store_true', help='print intended changes, write nothing')
    args = ap.parse_args()
    raw = args.spec.read_text(encoding='utf-8') if args.spec else sys.stdin.read()
    spec = json.loads(raw)
    result = scaffold(spec, args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
