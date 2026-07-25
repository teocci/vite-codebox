'''Build the codeblox binary, install it, and put it on the User environment.

    $VENV/python .claude/skills/codeblox-builder/scripts/install_codeblox.py
        [--install-dir D:\\apps\\codeblox] [--uninstall] [--dry-run] [--no-path]

Run --dry-run first. This is the only step in the skill that changes anything
outside the repo.

The install directory is an option with a default, never a constant: a hard-coded
absolute path in a committed script is the very thing this skill exists to avoid.

PATH is read from HKCU\\Environment through winreg, which returns the raw stored
value and its type. That matters twice over:

  * os.environ['PATH'] is the *machine* PATH merged with the user's. Writing that
    back to User scope would permanently copy every machine entry into the user's
    own PATH. This script never reads it.
  * A REG_EXPAND_SZ value holds references like %USERPROFILE%\\bin. Writing it
    back as REG_SZ would freeze them to today's expansion, so the original type
    is always preserved.
'''

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2

ENV_BIN = 'CODEBLOX_BIN'
BIN_NAME = 'codeblox'
PATH_VAR = 'Path'
ENV_KEY = r'Environment'

DEFAULT_INSTALL_DIR = Path(r'D:\apps\codeblox')
# Where `go build` runs, relative to the repo root.
CLI_DIR = Path('clients') / 'codeblox'
BUILD_TIMEOUT = 180


class InstallError(Exception):
    '''Something went wrong, with a message the operator can act on.'''


# ── the environment store ───────────────────────────────────────────────────

class WinregEnvStore:
    '''The real HKCU\\Environment, the only code here that touches the registry.

    Kept behind this seam so every rule about appending, de-duplicating, and
    preserving value types is testable against an in-memory fake.
    '''

    def __init__(self):
        if os.name != 'nt':
            raise InstallError(
                'the installer writes Windows User environment variables; '
                'on this platform, add the install dir to PATH yourself and set '
                f'${ENV_BIN} to the binary'
            )
        import winreg  # noqa: PLC0415 — Windows-only, imported where it is used
        self._winreg = winreg

    def get(self, name: str) -> tuple[str, int] | None:
        '''Return (raw value, registry type), or None when unset.'''
        winreg = self._winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY) as key:
            try:
                value, kind = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                return None
        return value, kind

    def set(self, name: str, value: str, kind: int) -> None:
        winreg = self._winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, name, 0, kind, value)

    def delete(self, name: str) -> None:
        winreg = self._winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass

    @property
    def default_kind(self) -> int:
        '''REG_SZ — what a plain string value is stored as.'''
        return self._winreg.REG_SZ


def normalise(entry: str) -> str:
    '''Fold an entry for comparison: case and a trailing slash do not matter.'''
    return entry.strip().rstrip('\\/').lower()


def split_path(value: str) -> list[str]:
    '''The real entries in a PATH value, for counting and matching.'''
    return [part for part in value.split(os.pathsep) if part.strip()]


def raw_entries(value: str) -> list[str]:
    '''Every element including the empty ones, for reconstructing a value.

    A stray `;` is not noise to be tidied away. An empty PATH element means "the
    current directory" on Windows, so removing one changes lookup behaviour —
    this installer adds one entry and must not quietly edit anything else.
    '''
    return value.split(os.pathsep) if value else []


class PathChange:
    '''What a PATH edit would do, computed without performing it.

    Planning and applying are separate so --dry-run reports the exact before and
    after a real run would produce, rather than a description of them.
    '''

    def __init__(self, before: str, after: str, kind: int):
        self.before = before
        self.after = after
        self.kind = kind

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def apply(self, store) -> None:
        if self.changed:
            store.set(PATH_VAR, self.after, self.kind)


def read_path(store) -> tuple[str, int]:
    '''The stored User PATH and its registry type; empty when unset.'''
    current = store.get(PATH_VAR)
    return current if current else ('', store.default_kind)


def plan_add(store, directory: Path) -> PathChange:
    '''Append directory to the User PATH.

    Idempotent: an entry already present — in any case, with or without a
    trailing separator — leaves the value untouched.
    '''
    value, kind = read_path(store)
    if any(normalise(entry) == normalise(str(directory)) for entry in split_path(value)):
        return PathChange(value, value, kind)

    # Append to the raw string rather than rejoining a parsed list, so every
    # existing character — including a trailing separator — survives verbatim.
    if not value:
        after = str(directory)
    elif value.endswith(os.pathsep):
        after = value + str(directory)
    else:
        after = value + os.pathsep + str(directory)
    return PathChange(value, after, kind)


def plan_remove(store, directory: Path) -> PathChange:
    '''Drop directory from the User PATH, leaving every other entry untouched.'''
    value, kind = read_path(store)
    kept = [e for e in raw_entries(value) if normalise(e) != normalise(str(directory))]
    return PathChange(value, os.pathsep.join(kept), kind)


def broadcast_change() -> None:
    '''Tell running programs the environment moved. Best effort by design.

    Already-open terminals keep their inherited copy regardless; this only helps
    programs that listen, so a failure here must never fail an install.
    '''
    if os.name != 'nt':
        return
    try:
        import ctypes  # noqa: PLC0415
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, 'Environment', 0x0002, 5000,
            ctypes.byref(ctypes.c_ulong()),
        )
    except Exception:  # noqa: BLE001 — advisory only
        pass


# ── build and copy ──────────────────────────────────────────────────────────

def binary_name() -> str:
    return BIN_NAME + '.exe' if os.name == 'nt' else BIN_NAME


def find_repo(start: Path) -> Path:
    '''The nearest ancestor holding clients/codeblox.'''
    for directory in [start, *start.parents]:
        if (directory / CLI_DIR).is_dir():
            return directory
    raise InstallError(
        f'no codeblox checkout found from {start} — run this from inside the repo'
    )


def build(repo: Path, run=None) -> Path:
    '''Compile the CLI into the repo's bin/ and return the artifact.'''
    run = run or subprocess.run
    bin_dir = repo / CLI_DIR / 'bin'
    out = bin_dir / binary_name()
    try:
        # -o <dir> rather than -o <file>: given a directory, Go names the binary
        # after the package and appends .exe on Windows. Naming the file
        # explicitly produces an extensionless artifact there, which `where.exe`
        # cannot find and CreateProcess will not launch.
        done = run(['go', 'build', '-o', str(bin_dir) + os.sep, '.'], cwd=str(repo / CLI_DIR),
                   capture_output=True, text=True, timeout=BUILD_TIMEOUT)
    except FileNotFoundError as exc:
        raise InstallError('go is not on PATH — install Go to build the CLI') from exc
    if done.returncode != 0:
        raise InstallError(f'go build failed:\n{done.stderr.strip()}')
    return out


def copy_into(source: Path, install_dir: Path) -> Path:
    '''Place the binary in its install directory, replacing any older copy.'''
    install_dir.mkdir(parents=True, exist_ok=True)
    target = install_dir / binary_name()
    shutil.copy2(source, target)
    return target


# ── orchestration ───────────────────────────────────────────────────────────

def install(install_dir: Path, repo: Path, store, dry_run: bool,
            touch_path: bool, run=None) -> dict:
    '''Build, install, and register. Returns a report of what happened.'''
    target = install_dir / binary_name()
    path_change = plan_add(store, install_dir) if touch_path else None
    report = {
        'action': 'install',
        'installDir': str(install_dir),
        'binary': str(target),
        'dryRun': dry_run,
        'pathBefore': path_change.before if path_change else None,
        'pathAfter': path_change.after if path_change else None,
        'pathChanged': bool(path_change and path_change.changed),
        f'{ENV_BIN}': str(target),
    }
    if dry_run:
        return report

    copy_into(build(repo, run), install_dir)
    if path_change:
        path_change.apply(store)
    store.set(ENV_BIN, str(target), store.default_kind)
    broadcast_change()

    report['version'] = verify(target, run)
    return report


def uninstall(install_dir: Path, store, dry_run: bool) -> dict:
    '''Remove the binary and only the environment entries this script added.'''
    target = install_dir / binary_name()
    path_change = plan_remove(store, install_dir)
    report = {
        'action': 'uninstall',
        'installDir': str(install_dir),
        'binary': str(target),
        'dryRun': dry_run,
        'pathBefore': path_change.before,
        'pathAfter': path_change.after,
        'pathChanged': path_change.changed,
    }
    if dry_run:
        return report

    path_change.apply(store)
    store.delete(ENV_BIN)
    target.unlink(missing_ok=True)
    broadcast_change()
    return report


def verify(target: Path, run=None) -> str:
    '''Prove the installed copy runs before declaring success.'''
    run = run or subprocess.run
    done = run([str(target), 'version'], capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise InstallError(
            f'{target} was installed but failed `version` (exit {done.returncode})'
        )
    return done.stdout.strip()


def describe(report: dict) -> str:
    '''Render a report for a human, with the PATH diff spelled out.'''
    lines = [f"{report['action']}: {report['binary']}"]
    if report['dryRun']:
        lines.append('DRY RUN — nothing was written')
    if report.get('version'):
        lines.append(f"verified: {report['version']}")

    if report['pathBefore'] is None:
        lines.append('PATH: left alone (--no-path)')
    elif not report['pathChanged']:
        lines.append('PATH: already correct, unchanged')
    else:
        before, after = report['pathBefore'], report['pathAfter']
        lines.append(f"PATH before ({len(split_path(before))} entries): {before}")
        lines.append(f"PATH after  ({len(split_path(after))} entries): {after}")
    if not report['dryRun']:
        lines.append('Open terminals keep the old environment until restarted.')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Build and install the codeblox binary, and register it on the User environment.',
        epilog='Run --dry-run first: this is the only step that changes anything outside the repo.',
    )
    parser.add_argument('--install-dir', type=Path, default=DEFAULT_INSTALL_DIR,
                        help=f'where the binary goes (default: {DEFAULT_INSTALL_DIR})')
    parser.add_argument('--uninstall', action='store_true',
                        help='remove the binary and the entries this script added')
    parser.add_argument('--dry-run', action='store_true',
                        help='report the exact PATH before/after and write nothing')
    parser.add_argument('--no-path', action='store_true',
                        help=f'install without touching PATH; ${ENV_BIN} is still set')
    parser.add_argument('--json', action='store_true', help='emit the report as JSON')
    args = parser.parse_args(argv)

    try:
        store = WinregEnvStore()
        if args.uninstall:
            report = uninstall(args.install_dir, store, args.dry_run)
        else:
            report = install(args.install_dir, find_repo(Path.cwd()), store,
                             args.dry_run, not args.no_path)
    except InstallError as exc:
        print(f'install_codeblox: {exc}', file=sys.stderr)
        return EXIT_USAGE

    if args.json:
        import json  # noqa: PLC0415 — only needed on this path
        print(json.dumps(report))
    else:
        print(describe(report))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
