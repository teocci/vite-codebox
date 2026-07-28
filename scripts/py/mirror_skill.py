'''Mirror the codeblox-builder skill from .claude/ to the other agent host dirs.

    $VENV/python scripts/py/mirror_skill.py            # propagate
    $VENV/python scripts/py/mirror_skill.py --check    # report drift, write nothing, exit 1

The skill ships to three hosts and is authored once, in .claude/. Their
frontmatter is identical, so the mirrors need no per-host adaptation — every
difference is drift, which is why a plain copy is the right mechanism and not a
templating step.

"Mirror", not "sync": the copy is strictly one-way. .claude/ is canonical and
overwrites the others; nothing ever flows back.

Only codeblox-builder is mirrored. The dev-phase-* skills are this repo's own
workflow tooling, never shipped to an agent host.

This is chore-track tooling and deliberately reachable only by running it. It is
not an npm script and does not run under `npm test`: what deploys from this repo
is the browser build and the ws server, and a stale mirror must never be able to
fail the suite that gates them.

Drift detection is therefore manual — run --check before committing a change to
the skill, propagate, and commit the mirrors as a chore.
'''

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_DRIFT = 1

# scripts/py/ -> repo root. Resolved from this file, never the cwd, so the
# script works from any directory.
ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / '.claude' / 'skills' / 'codeblox-builder'
MIRRORS = [
    ROOT / '.codex' / 'skills' / 'codeblox-builder',
    ROOT / '.agents' / 'skills' / 'codeblox-builder',
]

# Build artefacts, not content — they differ per interpreter run and ship nowhere.
IGNORED = {'__pycache__', '.pytest_cache'}


def files_under(root: Path) -> list[str]:
    '''Every file below root as a sorted list of posix-style relative paths.'''
    if not root.is_dir():
        return []
    found = []
    for path in root.rglob('*'):
        if any(part in IGNORED for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            found.append(path.relative_to(root).as_posix())
    return sorted(found)


def diff(source: Path, mirror: Path) -> tuple[list[str], list[str]]:
    '''(changed, stale) for one mirror: files to write, and files to remove.'''
    source_files = files_under(source)
    stale = [f for f in files_under(mirror) if f not in source_files]
    changed = [
        f for f in source_files
        if not (mirror / f).exists() or not filecmp.cmp(source / f, mirror / f, shallow=False)
    ]
    return changed, stale


def apply(source: Path, mirror: Path, changed: list[str], stale: list[str]) -> None:
    for f in stale:
        (mirror / f).unlink()
    for f in changed:
        target = mirror / f
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / f, target)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true',
                        help='report drift and exit 1 without writing anything')
    args = parser.parse_args(argv)

    source_files = files_under(SOURCE)
    # A guard, not a formality: every write path below deletes mirror files the
    # source does not have, so an empty source would silently empty both mirrors.
    if not source_files:
        print(f'[codeblox] refusing to mirror: no files under {rel(SOURCE)}', file=sys.stderr)
        return EXIT_DRIFT

    drifted = False
    for mirror in MIRRORS:
        name = rel(mirror)
        changed, stale = diff(SOURCE, mirror)

        if not changed and not stale:
            print(f'[codeblox] {name} up to date ({len(source_files)} files)')
            continue

        drifted = True
        if args.check:
            # Name the paths rather than diffing bytes: the useful signal is
            # which files were missed, not what changed inside them.
            for f in changed:
                print(f'[codeblox] {name} differs: {f}', file=sys.stderr)
            for f in stale:
                print(f'[codeblox] {name} has stale: {f}', file=sys.stderr)
            continue

        apply(SOURCE, mirror, changed, stale)
        print(f'[codeblox] {name} mirrored — {len(changed)} written, {len(stale)} removed')

    if args.check and drifted:
        print('[codeblox] mirrors are out of date — run this script without --check',
              file=sys.stderr)
        return EXIT_DRIFT
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
