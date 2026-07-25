'''Locate the codeblox binary. Nothing in this skill may hard-code its path.

Prints the resolved absolute path on stdout and exits 0, or exits 2 with an
actionable message naming the installer.

    $VENV/python .claude/skills/codeblox-builder/scripts/resolve_codeblox.py [--bin PATH] [--json]

Precedence, first hit wins:

    1. --bin PATH          the path the operator named
    2. $CODEBLOX_BIN       set by install_codeblox.py
    3. codeblox on PATH    the normal case once installed
    4. <repo>/clients/codeblox/bin/codeblox[.exe]   a dev checkout

This mirrors config.Endpoint in the CLI itself (flag -> env -> discovered ->
default), so the binary and the skill resolve things the same way.

A named-but-missing --bin or $CODEBLOX_BIN is a hard error, never a
fall-through: silently running a different binary than the operator named is
worse than failing.
'''

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Exit codes match the CLI's own taxonomy (internal/command/exit.go) so a caller
# sees one contract across the binary and its wrappers.
EXIT_OK = 0
EXIT_USAGE = 2

ENV_BIN = 'CODEBLOX_BIN'
BIN_NAME = 'codeblox'
# Where `npm run build:cli` puts it, relative to the repo root.
REPO_BIN = Path('clients') / 'codeblox' / 'bin'
# `codeblox version` must answer within this many seconds or the file is not a
# working binary, whatever the filesystem says.
VERSION_TIMEOUT = 10


class ResolutionError(Exception):
    '''No usable binary, with a message the caller can act on.'''


def executable(path: Path) -> bool:
    '''A file that exists and can be run.'''
    return path.is_file() and os.access(path, os.X_OK)


def candidate_names() -> list[str]:
    '''The binary's filename, .exe included on Windows.'''
    return [BIN_NAME + '.exe', BIN_NAME] if os.name == 'nt' else [BIN_NAME]


def repo_root(start: Path) -> Path | None:
    '''The nearest ancestor holding clients/codeblox — the dev-checkout case.'''
    for directory in [start, *start.parents]:
        if (directory / 'clients' / 'codeblox').is_dir():
            return directory
    return None


def named_path(raw: str, source: str) -> Path:
    '''Resolve an explicitly named binary, or fail loudly.'''
    path = Path(raw).expanduser()
    if not path.is_file():
        raise ResolutionError(f'{source} points at {path}, which does not exist')
    if not executable(path):
        raise ResolutionError(f'{source} points at {path}, which is not executable')
    return path.resolve()


def find(bin_flag: str | None, env: dict[str, str], cwd: Path,
         which=None) -> tuple[Path, str]:
    '''Return (path, source) for the first rung that answers.

    The host is injected so every rung is testable without touching the real
    PATH, environment, or filesystem layout. Injection points default to None
    and are resolved here rather than in the signature: a signature default
    binds at definition time, which would silently ignore a later patch.
    '''
    which = which or shutil.which
    if bin_flag:
        return named_path(bin_flag, '--bin'), 'flag'

    if env.get(ENV_BIN):
        return named_path(env[ENV_BIN], f'${ENV_BIN}'), 'env'

    found = which(BIN_NAME, path=env.get('PATH'))
    if found:
        return Path(found).resolve(), 'path'

    root = repo_root(cwd)
    if root:
        for name in candidate_names():
            local = root / REPO_BIN / name
            if executable(local):
                return local.resolve(), 'repo'

    raise ResolutionError(
        f'{BIN_NAME} not found. Install it with '
        f'`npm run install:cli`, or set ${ENV_BIN} to the binary, '
        f'or pass --bin PATH. Looked on $PATH and in <repo>/{REPO_BIN.as_posix()}/.'
    )


def version_of(path: Path, run=None) -> str:
    '''Confirm the file actually runs, and report what it says it is.

    A stale or half-written binary fails here rather than midway through a build.
    '''
    run = run or subprocess.run
    try:
        done = run([str(path), 'version'], capture_output=True, text=True,
                   timeout=VERSION_TIMEOUT)
    except OSError as exc:
        raise ResolutionError(f'{path} could not be executed: {exc}') from exc
    except subprocess.TimeoutExpired as exc:
        raise ResolutionError(f'{path} did not answer `version` in {VERSION_TIMEOUT}s') from exc

    if done.returncode != EXIT_OK:
        detail = (done.stderr or done.stdout).strip()
        raise ResolutionError(f'{path} failed `version` (exit {done.returncode}): {detail}')
    return done.stdout.strip()


def resolve(bin_flag: str | None, env: dict[str, str], cwd: Path,
            which=None, run=None) -> dict:
    '''Find the binary and prove it runs.'''
    path, source = find(bin_flag, env, cwd, which)
    return {'path': str(path), 'source': source, 'version': version_of(path, run)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Locate the codeblox binary.',
        epilog='Precedence: --bin, then $CODEBLOX_BIN, then $PATH, then a dev checkout.',
    )
    parser.add_argument('--bin', help='path to the binary; overrides every other source')
    parser.add_argument('--json', action='store_true',
                        help='emit {path, source, version} instead of the bare path')
    args = parser.parse_args(argv)

    try:
        found = resolve(args.bin, os.environ.copy(), Path.cwd())
    except ResolutionError as exc:
        print(f'resolve_codeblox: {exc}', file=sys.stderr)
        return EXIT_USAGE

    print(json.dumps(found) if args.json else found['path'])
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
