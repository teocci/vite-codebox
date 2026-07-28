'''dev-phase-start — scaffold tracking structure for an approved plan.

Reads a plan spec (JSON, via --spec FILE or stdin), allocates the next-free phase/item ids,
creates detail stubs, inserts in-progress index rows, adds planned PROGRESS rows, and writes
the PLAN.md ledger. Docs-only: never bumps the version, edits CHANGELOG, or runs git.

The ledger may hold more than one plan's rows. Scaffolding while a plan is active **appends** the
new group and never rewrites an existing row's phase/items/version/status — so a second plan can
be captured without losing the first. Write modes, decided from the current PLAN.md:

  fresh   missing, empty, a 'No active plan.' stub, or a header with zero rows -> full document
  append  one or more rows, at least one not released -> new rows appended, header preserved
  refuse  every row released (plan complete, not drained), or content that does not parse as a
          ledger. Exits 2 with a structured error and writes nothing.

Spec shape:
  {
    "approved": "2026-07-17", "branch": "feat/x", "cadence": "per-phase",
    "defers": ["P-1"],
    "phases": [
      {"title": "Command-scoped flags", "depends": [], "release": "R1",
       "items": [{"kind": "improvement", "title": "...", "summary": "one-line",
                  "objective": "...", "related": "siblings I-6"}]}
    ]
  }

"depends" entries order this spec's phases against each other and against the ledger:
  - an int is a 0-based index into this spec's "phases" array (an earlier phase only);
  - a string is an existing phase id, e.g. "P-4" -> the new phase waits for a ledger row.
"defers" is the reverse edge: existing *pending* phase ids that must now wait for this scaffold.
Each named row's Depends cell gains this run's terminal phases; nothing else in the row changes.

"release" is required per phase when appending — the R<n> default restarts at R1 each run and
would reopen a group the ledger already owns. "approved"/"branch"/"cadence" are honored on a
fresh write only; an append keeps the ledger's existing header.

    $VENV/python .claude/skills/dev-phase-start/scripts/scaffold.py --spec plan.json [--dry-run]
'''

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# skill scripts live at .claude/skills/<skill>/scripts/ -> parents[2] is the shared skills/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402

# The ledger table's header substrings — the same tuple tracklib parses PLAN.md with.
PLAN_COLS = ('Phase', 'Items', 'Status')
# Anchored stub test. tracklib.plan_is_stub uses an unanchored 'No active plan' in text, which
# also matches the phrase inside a note; here a false positive means overwriting a real ledger.
STUB_RE = re.compile(r'(?m)^\s*(?:[>*-]\s*)?No active plan\.?\s*$')
DIVIDER_RE = re.compile(r'\s*\|[\s:|-]+\|\s*$')
PLAN_ROW_CELLS = ('phase', 'items', 'depends', 'release', 'version', 'status')
EMPTY_CELLS = ('—', '-', '')


class Refusal(Exception):
    '''A precondition failed. Carries a machine-readable payload; nothing has been written.'''

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.payload = {'error': message, 'code': code, **extra}


def _refuse(code: str, message: str, **extra) -> Refusal:
    return Refusal(code, message, **extra)


@dataclass
class Allocation:
    '''Everything one scaffold run produces, before anything is written.'''

    planned: list[str] = field(default_factory=list)      # phase ids, in spec order
    plan_rows: list[dict] = field(default_factory=list)   # ledger row dicts
    files: dict[str, str] = field(default_factory=dict)   # path -> stub content
    imp_rows: list[str] = field(default_factory=list)
    fix_rows: list[str] = field(default_factory=list)
    prog_rows: list[str] = field(default_factory=list)


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


def next_phase_num(progress: str, existing: list[dict]) -> int:
    '''Next free phase number, from PROGRESS *and* the ledger.

    PROGRESS alone is not enough once the ledger can outlive a single run: if the two ever drift,
    reusing an id would put two rows with the same phase id in PLAN.md, and update_table_rows has
    no break — finalize/release would stamp both.
    '''
    nums = [_max_phase_num(progress)]
    nums += [int(m.group(1)) for r in existing
             if (m := re.fullmatch(r'P-(\d+)', r['phase']))]
    return max(nums) + 1


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


# ── the ledger: classify, render, edit ──────────────────────────────────────

def plan_row(r: dict) -> str:
    '''One ledger row. Shared by the fresh and append paths so the two cannot drift.'''
    return (f"| {r['phase']} | {r['items']} | {r['depends']} | {r['release']} "
            f"| (pending) | pending |")


def build_plan_md(meta: dict, rows: list[dict]) -> str:
    head = (f"# Active Plan\n\n"
            f"**Approved:** {meta.get('approved') or '(tbd)'}  "
            f"**Branch:** {meta.get('branch') or '(tbd)'}  "
            f"**Cadence:** {meta.get('cadence') or 'per-phase'}\n\n")
    tbl = ['| Phase | Items | Depends | Release | Version | Status |',
           '|-------|-------|---------|---------|---------|--------|']
    tbl.extend(plan_row(r) for r in rows)
    return head + '\n'.join(tbl) + '\n'


def _physical_rows(lines: list[str], hdr: int) -> int:
    '''Data lines physically under the ledger header, whether or not they parse.'''
    n = 0
    for i in range(hdr + 2, len(lines)):
        if not lines[i].lstrip().startswith('|'):
            break
        n += 1
    return n


def _stranded_rows(lines: list[str], start: int) -> int:
    '''Ledger-shaped rows below *start* — rows the contiguous table scan can never reach.

    Both tracklib readers stop at the first non-'|' line, so a merge-conflict marker under the
    divider makes a fully populated ledger parse as zero rows. Counting physical lines alone does
    not catch that (it stops at the same marker); this looks past the break for rows left behind.
    '''
    n = 0
    for line in lines[start:]:
        cell_line = line.strip()
        if not cell_line.startswith('|') or DIVIDER_RE.match(cell_line):
            continue
        if len(cell_line.strip('|').split('|')) >= len(PLAN_ROW_CELLS):
            n += 1
    return n


def classify_plan(text: str) -> str:
    '''Return the write mode for *text*: 'fresh' or 'append'. Refuses when unsure.

    'fresh' is returned only once there are provably zero data rows. Every state this cannot
    read confidently refuses instead of writing, because the write is a full replacement.

    Raises:
        Refusal: the ledger is unparseable, half-parseable, or complete but not drained.
    '''
    if not text.strip():
        return 'fresh'
    lines = text.splitlines()
    hdr = tl._find_header(lines, PLAN_COLS)
    if hdr is None:
        if STUB_RE.search(text):
            return 'fresh'
        raise _refuse('unparseable',
                      'PLAN.md has content but no Phase/Items/Status ledger table — refusing to '
                      "replace it. Reduce it to the 'No active plan.' stub to start fresh.")
    parsed, physical = tl.parse_plan(text)['rows'], _physical_rows(lines, hdr)
    stranded = _stranded_rows(lines, hdr + 2 + physical)
    if len(parsed) != physical:
        raise _refuse('malformed',
                      f'PLAN.md has {physical} table lines under the ledger header but only '
                      f'{len(parsed)} parse as 6-column rows — refusing to rewrite. Repair the '
                      f'malformed row(s) (a dropped cell?) and re-run.',
                      physical_rows=physical, parsed_rows=len(parsed))
    if stranded:
        raise _refuse('malformed',
                      f'PLAN.md has {stranded} ledger row(s) stranded below a non-table line — the '
                      f'table is fragmented (a merge conflict? stray text?) and everything past '
                      f'the break is invisible to the parser. Repair it and re-run.',
                      stranded_rows=stranded, parsed_rows=len(parsed))
    if not parsed:
        return 'fresh'
    if all(r['status'] == 'released' for r in parsed):
        raise _refuse('not-drained',
                      'every PLAN.md row is released — the plan is complete but not drained. Run '
                      'the §7b drain (delete the merged feat/* branch, prune any worktree), reset '
                      "PLAN.md to the 'No active plan.' stub, then re-run.",
                      released=[r['phase'] for r in parsed])
    return 'append'


def _dep_cells(cell: str) -> list[str]:
    return [d.strip() for d in cell.split(',') if d.strip() not in EMPTY_CELLS]


def _resolve_dep(dep, planned: list[str], known_ids: set[str], idx: int, title: str) -> str:
    if isinstance(dep, bool) or not isinstance(dep, (int, str)):
        raise _refuse('bad-depends',
                      f"phase '{title}': depends entry {dep!r} must be an int index into this "
                      f"spec's phases or an existing phase id string")
    if isinstance(dep, int):
        if not 0 <= dep < idx:
            raise _refuse('bad-depends',
                          f"phase '{title}': depends index {dep} is out of range — an int must be "
                          f"0..{idx - 1}, an earlier phase in this spec. To depend on a phase "
                          f"already in the ledger, name its id as a string.")
        return planned[dep]
    if dep not in known_ids:
        raise _refuse('unknown-depends',
                      f"phase '{title}': depends on unknown phase id '{dep}'",
                      known_ids=sorted(known_ids))
    return dep


def resolve_depends(deps: list, planned: list[str], known_ids: set[str], idx: int,
                    title: str) -> str:
    '''Render one phase's Depends cell from a mix of int indices and existing phase ids.'''
    out = [_resolve_dep(d, planned, known_ids, idx, title) for d in deps]
    return ', '.join(dict.fromkeys(out)) or '—'


def resolve_release(ph: dict, idx: int, mode: str, existing: list[dict]) -> str:
    '''The Release tag for one spec phase. Required when appending — the default would collide.'''
    release, title = ph.get('release'), ph.get('title', f'#{idx}')
    if mode != 'append':
        return release or f'R{idx + 1}'
    if not release:
        raise _refuse('release-required',
                      f"phase '{title}': 'release' is required when appending to an active plan — "
                      f"the default 'R{idx + 1}' restarts at R1 each run and would reopen a group "
                      f"the ledger already owns",
                      existing_releases=sorted({r['release'] for r in existing}))
    shipped = sorted({r['release'] for r in existing if r['status'] == 'released'})
    if release in shipped:
        raise _refuse('release-shipped',
                      f"phase '{title}': release '{release}' has already been cut — pick a tag "
                      f"that is not yet released",
                      released_releases=shipped)
    return release


def terminal_ids(alloc: Allocation) -> list[str]:
    '''This run's ids that no other phase in this run depends on — what a deferred row waits for.'''
    consumed = {d for r in alloc.plan_rows for d in _dep_cells(r['depends'])}
    return [p for p in alloc.planned if p not in consumed]


def _add_depends(terminals: list[str]):
    def transform(cells: list[str]) -> list[str]:
        merged = list(dict.fromkeys(_dep_cells(cells[2]) + terminals))
        return [cells[0], cells[1], ', '.join(merged), *cells[3:]]

    return transform


def apply_defers(text: str, defer_ids: list[str], terminals: list[str],
                 existing: list[dict]) -> str:
    '''Make each named existing row wait for *terminals*. Only the Depends cell is touched.'''
    by_id = {r['phase']: r for r in existing}
    for pid in defer_ids:
        row = by_id.get(pid)
        if row is None:
            raise _refuse('unknown-defers', f"cannot defer unknown phase id '{pid}'",
                          known_ids=sorted(by_id))
        if row['status'] != 'pending':
            raise _refuse('defer-not-pending',
                          f"cannot defer '{pid}' — it is '{row['status']}'. Only a pending phase "
                          f"can be made to wait for later work.")
        text = tl.update_table_rows(text, PLAN_COLS, tl.id_matcher(pid), _add_depends(terminals))
    return text


def detect_cycle(rows: list[dict]) -> list[str]:
    '''Phase ids left unorderable by a dependency cycle, sorted. Empty when the DAG is sound.'''
    satisfied = {r['phase'] for r in rows if r['status'] in ('done', 'released')}
    remaining = {r['phase']: set(r['depends_list']) for r in rows if r['phase'] not in satisfied}
    known = {r['phase'] for r in rows}
    progressed = True
    while progressed:
        progressed = False
        for pid, deps in list(remaining.items()):
            if (deps & known) <= satisfied:
                satisfied.add(pid)
                del remaining[pid]
                progressed = True
    return sorted(remaining)


# ── guards ───────────────────────────────────────────────────────────────────

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


def _meta_warnings(spec: dict, header: dict, root: Path) -> list[str]:
    '''An append keeps the ledger header, so say so when the spec or HEAD disagrees with it.'''
    out = []
    for key in ('branch', 'cadence'):
        want, have = spec.get(key), header.get(key)
        if want and have and want != have:
            out.append(f"spec {key} '{want}' differs from the ledger header '{have}' — the header "
                       f"is kept (one ledger, one header)")
    head, recorded = tl.git_branch(root), header.get('branch')
    if head and recorded and head != recorded:
        out.append(f"HEAD is '{head}' but the ledger header records branch '{recorded}' — §7b "
                   f"guard 3 acts on the header value")
    return out


# ── allocation ───────────────────────────────────────────────────────────────

def _allocate_items(ph: dict, alloc: Allocation, P, next_i: int, next_f: int) -> tuple[list, int, int]:
    item_ids = []
    for it in ph.get('items', []):
        if it['kind'] == 'fix':
            iid = f'F-{next_f}'; next_f += 1
            alloc.files[str(P('fixes_dir') / f'{iid}.md')] = item_stub(
                'fix', iid, it['title'], it.get('summary', ''), '', it.get('related', ''))
            alloc.fix_rows.append(f"| [{iid}](fixes/{iid}.md) | {it.get('summary', '(tbd)')} "
                                  f"| (tbd) | (tbd) |  |")
        else:
            iid = f'I-{next_i}'; next_i += 1
            alloc.files[str(P('improvements_dir') / f'{iid}.md')] = item_stub(
                'improvement', iid, it['title'], it.get('summary', ''),
                it.get('objective', ''), it.get('related', ''))
            alloc.imp_rows.append(f"| [{iid}](improvements/{iid}.md) | {it.get('summary', '(tbd)')} "
                                  f"| 🚧 In progress. |")
        item_ids.append(iid)
    return item_ids, next_i, next_f


def allocate(spec: dict, texts: dict, P, mode: str, existing: list[dict]) -> Allocation:
    '''Allocate ids, build stubs and rows for every phase in *spec*. Writes nothing.'''
    alloc = Allocation()
    # Item ids come from their index *and* the ledger's Items column, for the same reason phase
    # ids do: a reused id would put two same-id rows in front of finalize/release.
    next_phase = next_phase_num(texts['progress'], existing)
    next_i = max(_max_id(texts['improvements'], 'I'), _max_id(texts['plan'], 'I')) + 1
    next_f = max(_max_id(texts['fixes'], 'F'), _max_id(texts['plan'], 'F')) + 1
    known_ids = {r['phase'] for r in existing}

    for idx, ph in enumerate(spec['phases']):
        pnum = next_phase + idx
        pid = f'P-{pnum}'
        release = resolve_release(ph, idx, mode, existing)
        depends = resolve_depends(ph.get('depends', []), alloc.planned, known_ids, idx,
                                  ph.get('title', pid))
        item_ids, next_i, next_f = _allocate_items(ph, alloc, P, next_i, next_f)

        alloc.planned.append(pid)
        known_ids.add(pid)
        alloc.files[str(P('phases_dir') / f'phase-{pnum}.md')] = phase_stub(
            pnum, ph['title'], ph.get('objective', ''))
        alloc.prog_rows.append(f"| {pnum} | {ph['title']} | planned |")
        alloc.plan_rows.append({
            'phase': pid,
            'items': ', '.join(item_ids) if item_ids else '—',
            'depends': depends,
            'release': release,
        })
    return alloc


def render_plan(plan_text: str, mode: str, spec: dict, alloc: Allocation,
                existing: list[dict]) -> tuple[str, list[str]]:
    '''The new PLAN.md and the ids whose Depends cell was edited. Validates the resulting DAG.'''
    defer_ids = list(spec.get('defers') or [])
    if mode != 'append':
        if defer_ids:
            raise _refuse('defers-without-plan',
                          "'defers' names existing phases, but there is no active ledger to defer")
        return build_plan_md(_spec_meta(spec), alloc.plan_rows), []

    rows = [plan_row(r) for r in alloc.plan_rows]
    text = tl.append_table_rows(plan_text, PLAN_COLS, rows)
    if defer_ids:
        text = apply_defers(text, defer_ids, terminal_ids(alloc), existing)
    cycle = detect_cycle(tl.parse_plan(text)['rows'])
    if cycle:
        raise _refuse('cycle',
                      f"the resulting plan has a dependency cycle: {', '.join(cycle)} — refusing "
                      f"to write an unschedulable ledger",
                      cycle=cycle)
    return text, defer_ids


def _spec_meta(spec: dict) -> dict:
    return {k: spec.get(k) for k in ('approved', 'branch', 'cadence')}


def collect_edits(P, texts: dict, alloc: Allocation, plan_md: str) -> dict[str, str]:
    '''Every path this run writes, mapped to its full new content. Nothing touches disk here.'''
    edits = {}
    if alloc.imp_rows:
        edits[str(P('improvements'))] = tl.append_table_rows(
            texts['improvements'], ('ID', 'Idea', 'Notes'), alloc.imp_rows)
    if alloc.fix_rows:
        edits[str(P('fixes'))] = tl.append_table_rows(
            texts['fixes'], ('ID', 'Symptom', 'Fix'), alloc.fix_rows)
    edits[str(P('progress'))] = tl.append_table_rows(
        texts['progress'], ('Phase', 'Title', 'Status'), alloc.prog_rows)
    edits[str(P('plan'))] = plan_md
    edits.update(alloc.files)
    return edits


def scaffold(spec: dict, dry_run: bool) -> dict:
    root, cfg = tl.load()
    guard = _branch_guard(root, cfg)
    if guard and not dry_run:
        raise _refuse('release-branch', guard, branch=tl.git_branch(root))
    P = lambda k: tl.path_for(root, cfg, k)  # noqa: E731

    plan_text = tl.read(P('plan'))
    mode = classify_plan(plan_text)
    parsed = tl.parse_plan(plan_text)
    existing = parsed['rows'] if mode == 'append' else []

    texts = {k: tl.read(P(k)) for k in ('progress', 'improvements', 'fixes')}
    texts['plan'] = plan_text if mode == 'append' else ''
    alloc = allocate(spec, texts, P, mode, existing)
    plan_md, deferred = render_plan(plan_text, mode, spec, alloc, existing)

    edits = collect_edits(P, texts, alloc, plan_md)
    if not dry_run:
        for path, content in edits.items():
            tl.write(Path(path), content)

    warnings = _meta_warnings(spec, parsed['meta'], root) if mode == 'append' else []
    if guard:  # dry-run only reaches here; surface the branch warning without blocking the preview
        warnings.append(guard)
    return {
        'plan_mode': mode,
        'plan_rows_existing': len(existing),
        'phases': alloc.planned,
        'deferred': deferred,
        'improvements': list(alloc.imp_rows),
        'fixes': list(alloc.fix_rows),
        'files_created': list(alloc.files),
        'files_edited': [str(P(k)) for k in ('improvements', 'fixes', 'progress', 'plan')
                         if str(P(k)) in edits],
        'warnings': warnings,
        'dry_run': dry_run,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Scaffold an approved plan.')
    ap.add_argument('--spec', type=Path, help='plan spec JSON (default: stdin)')
    ap.add_argument('--dry-run', action='store_true', help='print intended changes, write nothing')
    args = ap.parse_args()
    raw = args.spec.read_text(encoding='utf-8') if args.spec else sys.stdin.read()
    spec = json.loads(raw)
    try:
        result = scaffold(spec, args.dry_run)
    except Refusal as exc:
        print(json.dumps(exc.payload, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
