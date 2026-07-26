'''One-call preflight: is everything needed to build actually working?

    $VENV/python .claude/skills/codeblox-builder/scripts/doctor.py [--json] [--bin PATH]

Checks the binary, the credential, and the server in one pass and reports the
first thing that is broken, with the remedy. Run this before diagnosing anything
by hand: the alternative is an agent inventing a troubleshooting sequence, which
is slower and reaches different conclusions on different runs.

The exit code is the CLI's own taxonomy, so the caller branches on an integer:
2 the binary is missing, 3 not authenticated, 4 the server is unreachable.
'''

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_codeblox as rc  # noqa: E402
import world  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NETWORK = 4

STATUS_TIMEOUT = 30


def check_binary(bin_flag: str | None) -> dict:
    '''Rung 1: is there a working binary, and which one did we pick?'''
    try:
        found = rc.resolve(bin_flag, os.environ.copy(), Path.cwd())
    except rc.ResolutionError as exc:
        return {'name': 'binary', 'ok': False, 'exit': EXIT_USAGE, 'detail': str(exc)}
    return {'name': 'binary', 'ok': True, 'detail': f"{found['version']} at {found['path']}",
            'path': found['path'], 'source': found['source']}


def check_auth(binary: str, run=None) -> dict:
    '''Rung 2: is there a credential the server accepts?

    `auth status` is the live check — `auth login` deliberately does not verify.
    '''
    run = run or subprocess.run
    try:
        done = run([binary, 'auth', 'status', '--json'], capture_output=True,
                   text=True, timeout=STATUS_TIMEOUT, env=os.environ.copy())
    except subprocess.TimeoutExpired:
        return {'name': 'auth', 'ok': False, 'exit': EXIT_NETWORK,
                'detail': f'`auth status` did not answer in {STATUS_TIMEOUT}s'}

    if done.returncode == EXIT_OK:
        return {'name': 'auth', 'ok': True, 'detail': summarise(done.stdout)}
    return {'name': 'auth', 'ok': False, 'exit': done.returncode,
            'detail': detail_of(done)}


def check_world(binary: str) -> dict:
    '''Rung 3: does the server answer with a contract we can build against?'''
    try:
        contract = world.fetch(binary)
    except world.WorldError as exc:
        return {'name': 'world', 'ok': False, 'exit': EXIT_NETWORK, 'detail': str(exc)}

    view = world.digest(contract)
    bounds = view['bounds']
    # Preflight has the contract in hand and is the first thing anything runs, so
    # it is the cheapest place to learn the scale. Reporting only blocks is what
    # left "a block is a metre" as the standing assumption downstream.
    per_metre = view.get('blocksPerMetre')
    scale = f"block {view['blockLabel']}"
    if per_metre:
        scale += f" = {per_metre:g} blocks per metre"
    return {
        'name': 'world', 'ok': True,
        'detail': (f"{scale}; {view['materialCount']} materials, ops "
                   f"{', '.join(sorted(view['ops']))}; "
                   f"y {bounds['y'][0]}..{bounds['y'][1]}, "
                   f"x/z ±{bounds['x'][1]} blocks"),
        'bounds': bounds,
        'blocksPerMetre': per_metre,
    }


def detail_of(done) -> str:
    '''The reason from a failed CLI call — envelope first, then raw text.'''
    text = (done.stderr or done.stdout).strip()
    try:
        return json.loads(text).get('detail', text)
    except json.JSONDecodeError:
        return text


def summarise(stdout: str) -> str:
    '''Condense `auth status --json` into one line, never echoing the token.'''
    try:
        status = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip()
    parts = [f'{key}={value}' for key, value in status.items()
             if key.lower() not in ('token', 'secret')]
    return ', '.join(parts)


def run_checks(bin_flag: str | None) -> tuple[list[dict], int]:
    '''Run each rung, stopping at the first failure. Returns (checks, exit).'''
    binary_check = check_binary(bin_flag)
    if not binary_check['ok']:
        return [binary_check], binary_check['exit']

    checks = [binary_check]
    for check in (check_auth(binary_check['path']), ):
        checks.append(check)
        if not check['ok']:
            return checks, check['exit']

    world_check = check_world(binary_check['path'])
    checks.append(world_check)
    return checks, EXIT_OK if world_check['ok'] else world_check['exit']


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Preflight the codeblox binary, credential, and server in one call.',
    )
    parser.add_argument('--bin', help='path to the codeblox binary')
    parser.add_argument('--json', action='store_true', help='emit the report as JSON')
    args = parser.parse_args(argv)

    checks, code = run_checks(args.bin)

    if args.json:
        print(json.dumps({'ok': code == EXIT_OK, 'exit': code, 'checks': checks}))
    else:
        for check in checks:
            mark = 'ok  ' if check['ok'] else 'FAIL'
            print(f"[{mark}] {check['name']:<7} {check['detail']}")
        if code != EXIT_OK:
            # Flush first: the streams are buffered independently, so without
            # this the summary can surface above the checks it summarises.
            sys.stdout.flush()
            print(f'preflight failed (exit {code})', file=sys.stderr)
    return code


if __name__ == '__main__':
    sys.exit(main())
