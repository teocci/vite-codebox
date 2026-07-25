'''Shared helpers for the dev-phase-* skill scripts (project-agnostic).

Reads project bindings from ``docs/conventions/tracking.md`` (a fenced ``toml`` block) and
provides parsing/IO utilities for the tracking files. This is the dev-phase-* family's single shared
library: it lives once here in the ``dev-phase-lib`` skill and every ``dev-phase-*`` script imports it via
the uniform bootstrap (see any consumer, e.g. ``dev-phase-workflow/scripts/order.py``). The unit of
portability is the family — ``dev-phase-lib`` travels with its consumers — not one skill directory.
'''

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

DEFAULTS = {
    'package': None,
    'version_file': 'src/__init__.py',
    'version_attr': '__version__',
    'version_dynamic': False,
    'test_cmd': 'pytest',
    # Branch / integration / concurrency policy (base defaults; tracking.md overrides — see
    # conventions §7b). 'trunk' + 'single' is the safest zero-config default: commit and release
    # on the release branch, one working dir. A repo using feature branches sets integration =
    # 'branch' and (optionally) concurrency = 'hybrid'/'worktree'.
    'release_branch': 'main',
    'integration': 'trunk',
    'concurrency': 'single',
    'paths': {
        'progress': 'docs/PROGRESS.md',
        'plan': 'docs/PLAN.md',
        'release_index': 'docs/RELEASE.md',
        'changelog': 'CHANGELOG.md',
        'improvements': 'docs/IMPROVEMENTS.md',
        'fixes': 'docs/FIXES.md',
        'phases_dir': 'docs/phases',
        'improvements_dir': 'docs/improvements',
        'fixes_dir': 'docs/fixes',
    },
}


def find_root(start: Path | None = None) -> Path:
    '''Walk up from *start* (cwd) to the dir holding tracking.md or a .git.'''
    base = (start or Path.cwd()).resolve()
    for cand in [base, *base.parents]:
        if (cand / 'docs' / 'conventions' / 'tracking.md').exists():
            return cand
        if (cand / '.git').exists():
            return cand
    return base


def load(start: Path | None = None) -> tuple[Path, dict]:
    '''Return (repo_root, merged_config). tracking.md overrides DEFAULTS.'''
    root = find_root(start)
    cfg = {k: v for k, v in DEFAULTS.items() if k != 'paths'}
    cfg['paths'] = dict(DEFAULTS['paths'])
    tf = root / 'docs' / 'conventions' / 'tracking.md'
    if tf.exists():
        m = re.search(r'```toml\s*\n(.*?)```', tf.read_text(encoding='utf-8'), re.S)
        if m:
            data = tomllib.loads(m.group(1))
            paths = data.pop('paths', {})
            cfg.update(data)
            cfg['paths'].update(paths)
    return root, cfg


def path_for(root: Path, cfg: dict, key: str) -> Path:
    return root / cfg['paths'][key]


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def read_version(root: Path, cfg: dict) -> str | None:
    '''Read the version out of <version_file>.

    Accepts both assignment (``__version__ = '1.2.3'`` — Python/JS) and mapping
    (``"version": "1.2.3"`` — JSON/YAML) forms so one helper serves any project language.
    '''
    vf = root / cfg['version_file']
    if not vf.exists():
        return None
    attr = re.escape(cfg.get('version_attr', '__version__'))
    m = re.search(attr + r"\s*[:=]\s*['\"]([^'\"]+)['\"]", vf.read_text(encoding='utf-8'))
    return m.group(1) if m else None


def is_semver(s: str | None) -> bool:
    return bool(s) and bool(SEMVER_RE.match(s))


# ── PLAN.md ────────────────────────────────────────────────────────────────

def plan_is_stub(text: str) -> bool:
    return 'No active plan' in text or not _plan_table_rows(text)


def parse_plan(text: str) -> dict:
    '''Parse the active-plan ledger into {meta, rows}. rows are dicts.'''
    meta = {}
    for key in ('Approved', 'Branch', 'Cadence'):
        m = re.search(r'\*\*' + key + r':\*\*\s*([^\n*]+?)(?:\s{2,}\*\*|\n)', text)
        if m:
            meta[key.lower()] = m.group(1).strip()
    return {'meta': meta, 'rows': _plan_table_rows(text)}


def _plan_table_rows(text: str) -> list[dict]:
    cols = ['phase', 'items', 'depends', 'release', 'version', 'status']
    rows = []
    for cells in _iter_table_rows(text, header_contains=('Phase', 'Items', 'Status')):
        if len(cells) < len(cols):
            continue
        row = {c: cells[i].strip() for i, c in enumerate(cols)}
        row['depends_list'] = [] if row['depends'] in ('—', '-', '') else [
            d.strip() for d in row['depends'].split(',') if d.strip()
        ]
        row['items_list'] = [i.strip() for i in row['items'].split(',') if i.strip() and i.strip() not in ('—', '-')]
        rows.append(row)
    return rows


def plan_cursor(rows: list[dict]) -> dict | None:
    '''Topmost non-released row whose deps are all done/released.'''
    done = {r['phase'] for r in rows if r['status'] in ('done', 'released')}
    for r in rows:
        if r['status'] == 'released':
            continue
        if all(d in done for d in r['depends_list']):
            return r
    return None


def plan_ready(rows: list[dict]) -> list[dict]:
    '''All not-yet-done phases whose deps are all done (parallel candidates).'''
    done = {r['phase'] for r in rows if r['status'] in ('done', 'released')}
    return [
        r for r in rows
        if r['status'] not in ('done', 'released') and all(d in done for d in r['depends_list'])
    ]


# ── generic markdown-table iteration ─────────────────────────────────────────

def _iter_table_rows(text: str, header_contains: tuple[str, ...]):
    '''Yield data-row cell-lists for the first table whose header has all substrings.'''
    lines = text.splitlines()
    in_table = False
    for i, line in enumerate(lines):
        if not in_table:
            if line.lstrip().startswith('|') and all(h in line for h in header_contains):
                # next line must be the divider
                if i + 1 < len(lines) and re.match(r'\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
                    in_table = True
            continue
        if not line.lstrip().startswith('|'):
            break
        if re.match(r'\s*\|[\s:|-]+\|\s*$', line):
            continue  # divider
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        yield cells


# ── table editing (write) ────────────────────────────────────────────────────

def _find_header(lines: list[str], header_contains: tuple[str, ...]) -> int | None:
    for idx, line in enumerate(lines):
        if line.lstrip().startswith('|') and all(h in line for h in header_contains):
            if idx + 1 < len(lines) and re.match(r'\s*\|[\s:|-]+\|\s*$', lines[idx + 1]):
                return idx
    return None


def _last_data_row(lines: list[str], hdr: int) -> int:
    last = hdr + 1  # the divider
    i = hdr + 2
    while i < len(lines) and lines[i].lstrip().startswith('|'):
        last = i
        i += 1
    return last


def append_table_rows(text: str, header_contains: tuple[str, ...], new_rows: list[str]) -> str:
    lines = text.splitlines()
    hdr = _find_header(lines, header_contains)
    if hdr is None:
        raise ValueError(f'table not found for header {header_contains}')
    last = _last_data_row(lines, hdr)
    out = lines[:last + 1] + list(new_rows) + lines[last + 1:]
    return '\n'.join(out) + ('\n' if text.endswith('\n') else '')


def prepend_table_rows(text: str, header_contains: tuple[str, ...], new_rows: list[str]) -> str:
    '''Insert rows immediately after the divider (newest-first tables).'''
    lines = text.splitlines()
    hdr = _find_header(lines, header_contains)
    if hdr is None:
        raise ValueError(f'table not found for header {header_contains}')
    at = hdr + 2  # after header + divider
    out = lines[:at] + list(new_rows) + lines[at:]
    return '\n'.join(out) + ('\n' if text.endswith('\n') else '')


def update_table_rows(text: str, header_contains: tuple[str, ...], key_pred, transform) -> str:
    '''Rewrite each data row where key_pred(cells) is true via transform(cells)->cells.'''
    lines = text.splitlines()
    hdr = _find_header(lines, header_contains)
    if hdr is None:
        raise ValueError(f'table not found for header {header_contains}')
    for i in range(hdr + 2, len(lines)):
        if not lines[i].lstrip().startswith('|'):
            break
        if re.match(r'\s*\|[\s:|-]+\|\s*$', lines[i]):
            continue
        cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        if key_pred(cells):
            lines[i] = '| ' + ' | '.join(transform(cells)) + ' |'
    return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')


# ── CHANGELOG.md ─────────────────────────────────────────────────────────────

def changelog_unreleased(text: str) -> list[str]:
    '''Bullet lines under ## [Unreleased] up to the next ## heading.'''
    m = re.search(r'(?ms)^##\s*\[Unreleased\][^\n]*\n(.*?)(?=^##\s|\Z)', text)
    if not m:
        return []
    return [ln for ln in m.group(1).splitlines() if ln.strip().startswith('-')]


def changelog_top_version(text: str) -> str | None:
    '''First ## [X.Y.Z] heading (skipping Unreleased).'''
    for m in re.finditer(r'##\s*\[([^\]]+)\]', text):
        tag = m.group(1)
        if tag.lower() == 'unreleased':
            continue
        return tag.split()[0] if tag else None
    return None


# ── git ──────────────────────────────────────────────────────────────────────

def git_porcelain(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ['git', '-C', str(root), 'status', '--porcelain'],
            capture_output=True, text=True, check=True,
        ).stdout
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def git_branch(root: Path) -> str:
    try:
        return subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return ''


def git_latest_tag(root: Path) -> str:
    '''Most recent tag reachable from HEAD (git describe --tags --abbrev=0), '' if none. Read-only.'''
    try:
        return subprocess.run(
            ['git', '-C', str(root), 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return ''


def git_ahead_behind(root: Path, base: str) -> tuple[int, int] | None:
    '''(ahead, behind) of HEAD vs *base*, or None if base is unknown/unreachable.

    Read-only. ``ahead`` = commits on HEAD not on *base* (need integrating); ``behind`` =
    commits on *base* not on HEAD (need pulling). Returns (0, 0) when HEAD is *base* itself.
    '''
    try:
        out = subprocess.run(
            ['git', '-C', str(root), 'rev-list', '--left-right', '--count', f'{base}...HEAD'],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        behind, ahead = int(out[0]), int(out[1])
        return ahead, behind
    except Exception:
        return None
