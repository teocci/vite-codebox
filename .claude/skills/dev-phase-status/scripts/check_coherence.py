'''dev-phase-status — release-coherence checker.

Read-only assertions that the tracking files agree with the version single-source-of-truth.
Exit non-zero on any failure (a hard gate for dev-phase-complete Part B). With --advisory it
prints findings and always exits 0 (used by the status report).

    $VENV/python .claude/skills/dev-phase-status/scripts/check_coherence.py [--advisory]
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


def _detail_files_for_version(root: Path, cfg: dict, version: str) -> list[Path]:
    hits = []
    for key in ('phases_dir', 'improvements_dir', 'fixes_dir'):
        d = root / cfg['paths'][key]
        if not d.exists():
            continue
        for f in d.glob('*.md'):
            text = f.read_text(encoding='utf-8')
            m = re.search(r'\*\*Version:\*\*\s*([^\n]+)', text)
            if m and m.group(1).strip() == version:
                hits.append(f)
    return hits


def run_checks() -> list[tuple[bool, str]]:
    root, cfg = tl.load()
    results: list[tuple[bool, str]] = []

    version = tl.read_version(root, cfg)
    results.append((tl.is_semver(version), f'__version__ is semver: {version!r}'))

    if cfg.get('version_dynamic'):
        pyproject = tl.read(root / 'pyproject.toml')
        literal = re.search(r'(?m)^\s*version\s*=\s*["\']', pyproject)
        results.append((not literal, 'pyproject.toml has no literal version= (dynamic intact)'))

    changelog = tl.read(tl.path_for(root, cfg, 'changelog'))
    top = tl.changelog_top_version(changelog)
    results.append((top == version, f'CHANGELOG top [{top}] == __version__ {version}'))

    rel_text = tl.read(tl.path_for(root, cfg, 'release_index'))
    rel_top = _release_top_version(rel_text)
    if rel_top is not None:
        results.append((rel_top == version, f'RELEASE.md top row {rel_top} == __version__ {version}'))

    if version:
        stale = [f.name for f in _detail_files_for_version(root, cfg, version)
                 if '✅ DONE' not in f.read_text(encoding='utf-8')]
        results.append((not stale, f'all v{version} detail files are ✅ DONE'
                        + (f' (stale: {stale})' if stale else '')))

    # Invariant: <RELEASE_BRANCH> HEAD == latest release (conventions §7b). Only assertable when
    # actually on the release branch — off it (e.g. Part B runs the gate on the plan branch first)
    # this is skipped, so it never false-fails the pre-integration coherence gate.
    branch = tl.git_branch(root)
    release_branch = cfg.get('release_branch', 'main')
    if version and branch and branch == release_branch:
        tag = tl.git_latest_tag(root)
        results.append((tag in (version, f'v{version}'),
                        f'on {release_branch}: latest reachable tag {tag!r} == v{version} '
                        f'({release_branch} is the released truth)'))
    return results


def _release_top_version(text: str) -> str | None:
    # table row: | v0.2.0 | ... |
    m = re.search(r'(?m)^\|\s*v?(\d+\.\d+\.\d+)\s*\|', text)
    if m:
        return m.group(1)
    # legacy prose: ## 0.2.0 - date
    m = re.search(r'(?m)^##\s*v?(\d+\.\d+\.\d+)\b', text)
    return m.group(1) if m else None


def _emit_text(results: list[tuple[bool, str]], failed: int) -> None:
    for ok, msg in results:
        print(f'[{"OK  " if ok else "FAIL"}] {msg}')
    print(f'\n{failed} coherence check(s) failed.' if failed else '\nAll coherence checks passed.')


def _emit_json(results: list[tuple[bool, str]], failed: int) -> None:
    payload = {
        'ok': failed == 0,
        'failed': failed,
        'checks': [{'ok': ok, 'msg': msg} for ok, msg in results],
    }
    print(json.dumps(payload, separators=(',', ':')))


def main() -> int:
    ap = argparse.ArgumentParser(description='Release-coherence gate.')
    ap.add_argument('--advisory', action='store_true', help='report only; always exit 0')
    ap.add_argument('--json', action='store_true', help='emit one compact JSON line')
    args = ap.parse_args()
    results = run_checks()
    failed = sum(1 for ok, _ in results if not ok)
    (_emit_json if args.json else _emit_text)(results, failed)
    return 0 if args.advisory else (1 if failed else 0)


if __name__ == '__main__':
    raise SystemExit(main())
