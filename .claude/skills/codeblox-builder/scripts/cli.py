'''Run one codeblox verb against the resolved binary.

    $VENV/python .claude/skills/codeblox-builder/scripts/cli.py <verb> [args...]

This script has no flags of its own: every argument forwards verbatim, and the
exit code and both streams come back unchanged. It exists so a caller can reach
a one-shot verb -- `clear`, `view 4` -- without hard-coding a path to the binary.
That is the whole job. `submit.py` runs batches and `doctor.py` preflights;
neither forwards an arbitrary verb, and a caller that improvised one would be
choosing a binary by guess.

Written for the `/codeblox:*` slash commands, which run it at prompt expansion.
Because they do, the argument list is fixed by the command file rather than
composed at runtime, and validation belongs to the CLI: it already refuses a bad
verb with exit 2 and a message naming the valid set. Re-checking here would be a
second, staler copy of that list.
'''

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_codeblox as rc  # noqa: E402

# The CLI's own taxonomy (internal/command/exit.go), shared by every wrapper.
EXIT_USAGE = 2


def forward(argv: list[str], env: dict[str, str], cwd: Path,
            which=None, run=None) -> int:
    '''Resolve the binary and run argv against it, returning its exit code.

    The host is injected so the whole path is testable without a real binary.

    Uses `rc.find` rather than `rc.resolve`: `resolve` proves the file runs by
    calling `codeblox version` first, which is worth a subprocess before a long
    build and not before a single verb that would fail the same way one line
    later.
    '''
    run = run or subprocess.run
    try:
        binary, _ = rc.find(None, env, cwd, which)
    except rc.ResolutionError as exc:
        print(f'cli: {exc}', file=sys.stderr)
        return EXIT_USAGE

    # Streams are inherited, not captured: the output is read by a person, and
    # buffering it here would only delay it and lose the stdout/stderr split.
    return run([str(binary), *argv], env=env).returncode


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('cli: needs a codeblox verb, for example `clear` or `view 4`', file=sys.stderr)
        return EXIT_USAGE
    return forward(argv, os.environ.copy(), Path.cwd())


if __name__ == '__main__':
    sys.exit(main())
