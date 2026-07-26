'''dev-phase-complete Part B — cut a release (mechanical bookkeeping).

Given the version, date, theme, test count, and the phase/item ids in the release group:
  1. bump the version single-source-of-truth (version_file only)
  2. roll CHANGELOG [Unreleased] into ## [X.Y.Z] - date (+ theme), leaving a fresh [Unreleased]
  3. prepend a RELEASE.md index row (release -> phases)
  4. stamp Version/Date/Status/Tests in each phase & item detail file
  5. mark improvement index Notes done; fill fix index Phase column
  6. mark the plan rows released (+ version); update PROGRESS **Current version:**

Does NOT commit/tag/push (the skill does that after check_coherence.py passes) — this only edits
files. Compute the version with the base version-map; pass it in.

    $VENV/python .claude/skills/dev-phase-complete/scripts/cut_release.py \
        --version 0.3.0 --date 2026-07-17 --tests 432 --theme "..." \
        --phases P-15 --improvements I-5 [--fixes F-4] [--dry-run]
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


def _stamp_detail(text: str, version: str, date: str, tests: int) -> str:
    status = f'✅ DONE ({tests} tests; live-verified).'
    text = re.sub(r'(\*\*Version:\*\*\s*)\(pending\)', rf'\g<1>{version}', text)
    text = re.sub(r'(\*\*Date:\*\*\s*)\(pending\)', rf'\g<1>{date}', text)
    text = re.sub(r'(\*\*Tests:\*\*\s*)\(pending\)', rf'\g<1>{tests}', text)
    text = re.sub(r'(\*\*Status:\*\*\s*)🚧 IN PROGRESS', rf'\g<1>{status}', text)
    return text


def _roll_changelog(text: str, version: str, date: str, theme: str) -> str:
    m = re.search(r'(?ms)^(##\s*\[Unreleased\][^\n]*\n)(.*?)(?=^##\s|\Z)', text)
    if not m:
        raise ValueError('CHANGELOG has no ## [Unreleased] section')
    body = m.group(2).strip('\n')
    block = f'## [Unreleased]\n\n## [{version}] - {date}\n\n'
    if theme:
        block += theme.strip() + '\n\n'
    if body:
        block += body + '\n\n'
    return text[:m.start()] + block + text[m.end():]


def cut(args: argparse.Namespace) -> dict:
    root, cfg = tl.load()
    P = lambda k: tl.path_for(root, cfg, k)  # noqa: E731
    version, date, tests, theme = args.version, args.date, args.tests, args.theme or ''
    if not tl.is_semver(version):
        raise SystemExit(f'--version {version!r} is not semver')

    edits: dict[Path, str] = {}
    actions = []

    # 1. version bump (version_file only) — raises if no literal matched, so a drifted
    # version_file fails here rather than surfacing later as a coherence-gate mismatch.
    vf = root / cfg['version_file']
    edits[vf] = tl.bump_version_text(vf.read_text(encoding='utf-8'), cfg['version_attr'],
                                     version, where=cfg['version_file'])
    actions.append(f'bump {cfg["version_file"]} -> {version}')

    # 2. changelog roll
    cl = P('changelog')
    edits[cl] = _roll_changelog(tl.read(cl), version, date, theme)
    actions.append(f'CHANGELOG [Unreleased] -> [{version}]')

    # 3. RELEASE.md index row
    ri = P('release_index')
    phases_disp = ', '.join(args.phases)
    row = f'| v{version} | {date} | {phases_disp} | {theme[:60]} |'
    edits[ri] = tl.prepend_table_rows(tl.read(ri), ('Release', 'Date', 'Phases'), [row])
    actions.append(f'RELEASE.md += v{version}')

    # 4. detail files
    for p in args.phases:
        n = re.search(r'\d+', p).group(0)
        f = P('phases_dir') / f'phase-{n}.md'
        if f.exists():
            edits[f] = _stamp_detail(tl.read(f), version, date, tests)
            actions.append(f'stamp phase-{n}.md')
    for iid in args.improvements or []:
        f = P('improvements_dir') / f'{iid}.md'
        if f.exists():
            edits[f] = _stamp_detail(tl.read(f), version, date, tests)
            actions.append(f'stamp {iid}.md')
    for fid in args.fixes or []:
        f = P('fixes_dir') / f'{fid}.md'
        if f.exists():
            edits[f] = _stamp_detail(tl.read(f), version, date, tests)
            actions.append(f'stamp {fid}.md')

    # 5. index rows: improvements Notes done-marker; fixes Phase column
    if args.improvements:
        imp = P('improvements')
        text = tl.read(imp)
        for iid in args.improvements:
            text = tl.update_table_rows(
                text, ('ID', 'Idea', 'Notes'),
                key_pred=tl.id_matcher(iid),
                transform=lambda c: c[:-1] + [_done_note(c[-1], version)],
            )
        edits[imp] = text
        actions.append('IMPROVEMENTS Notes done-marked')
    if args.fixes:
        fx = P('fixes')
        text = tl.read(fx)
        for fid in args.fixes:
            text = tl.update_table_rows(
                text, ('ID', 'Symptom', 'Fix'),
                key_pred=tl.id_matcher(fid),
                transform=lambda c: c[:-1] + [version],
            )
        edits[fx] = text
        actions.append('FIXES Phase column filled')

    # 6. plan rows -> released; PROGRESS current version
    plan = P('plan')
    ptext = tl.read(plan)
    for p in args.phases:
        pid = f'P-{re.search(r"[0-9]+", p).group(0)}'
        ptext = tl.update_table_rows(
            ptext, ('Phase', 'Items', 'Status'),
            key_pred=tl.id_matcher(pid),
            transform=lambda c: [c[0], c[1], c[2], c[3], version, 'released'],
        )
    edits[plan] = ptext
    prog = P('progress')
    edits[prog] = re.sub(r'(\*\*Current version:\*\*\s*)[^\n]+',
                         rf'\g<1>{version}', tl.read(prog), count=1)
    actions.append(f'PLAN released; PROGRESS Current version -> {version}')

    if not args.dry_run:
        for path, content in edits.items():
            tl.write(path, content)

    return {'version': version, 'actions': actions,
            'files': [str(p) for p in edits], 'dry_run': args.dry_run}


def _done_note(note: str, version: str) -> str:
    note = note.replace('🚧 In progress.', '').strip()
    marker = f'✅ Done in v{version}.'
    if marker in note:
        return note
    return (note + ' ' + marker).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description='Cut a release (Part B).')
    ap.add_argument('--version', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--tests', type=int, required=True)
    ap.add_argument('--theme', default='')
    ap.add_argument('--phases', nargs='+', required=True)
    ap.add_argument('--improvements', nargs='*')
    ap.add_argument('--fixes', nargs='*')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    print(json.dumps(cut(args), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
