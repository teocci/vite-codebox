'''Fetch the server's published contract and reduce it to a token-small digest.

    $VENV/python .claude/skills/codeblox-builder/scripts/world.py [--refresh] [--json] [--bin PATH]

Nothing about ops or materials is written into this skill. The op list, their
field types, the palette, and the world extent all come from `codeblox info`,
which is the whole point of the server publishing a contract: a new material or
a new op needs no change here.

This module also owns the *anchoring rule* — how a command's `at` maps to the
box it occupies. That rule is the one piece of geometry the contract does NOT
publish (it types fields, it does not describe shapes), so it is written down
once, here, and imported by both shapes.py and submit.py rather than being
re-derived in each. `tests/test_world.py` pins it, and an end-to-end test in
clients/codeblox/tests/ checks it against a live server so drift fails loudly.
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

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NETWORK = 4

INFO_TIMEOUT = 30


class WorldError(Exception):
    '''The contract could not be fetched or understood.'''


def fetch(binary: str, refresh: bool = False, run=None, env=None) -> dict:
    '''Run `codeblox info --json` and return the parsed contract.

    The CLI caches the contract at ~/.codeblox/world_info.json and serves reads
    from there, so this is cheap to call repeatedly. --refresh forces a fetch.
    '''
    run = run or subprocess.run
    argv = [binary, 'info', '--json']
    if refresh:
        argv.append('--refresh')
    try:
        done = run(argv, capture_output=True, text=True, timeout=INFO_TIMEOUT,
                   env=env if env is not None else os.environ.copy())
    except subprocess.TimeoutExpired as exc:
        raise WorldError(f'`codeblox info` did not answer in {INFO_TIMEOUT}s') from exc

    if done.returncode != EXIT_OK:
        raise WorldError((done.stderr or done.stdout).strip() or
                         f'`codeblox info` failed with exit {done.returncode}')
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise WorldError(f'`codeblox info` did not emit JSON: {exc}') from exc


# ── the digest ──────────────────────────────────────────────────────────────

def digest(contract: dict) -> dict:
    '''Reduce the contract to what a builder actually needs to decide.

    The palette is grouped by family rather than listed flat: the choice a
    builder makes is "something glassy", and the family is what answers it.
    '''
    config = contract.get('config', {})
    palette = contract.get('palette', {})

    families: dict[str, list[str]] = {}
    for name, material in sorted(palette.items()):
        families.setdefault(material.get('family', 'unknown'), []).append(name)

    return {
        'blockSize': config.get('blockSize'),
        'blockLabel': config.get('blockLabel'),
        'bounds': bounds_of(contract),
        'extentMetres': config.get('extent'),
        'materialCount': len(palette),
        'families': families,
        'ops': {op['op']: op.get('fields', {}) for op in contract.get('ops', [])},
    }


def bounds_of(contract: dict) -> dict:
    '''The buildable box, in blocks.

    Horizontal axes run from -boundBlocks to +boundBlocks; the vertical runs
    from 0 (the floor) to heightBlocks. The floor is the asymmetry worth
    remembering — negative Y is never valid.
    '''
    config = contract.get('config', {})
    bound = config.get('boundBlocks', 0)
    height = config.get('heightBlocks', 0)
    return {
        'x': [-bound, bound],
        'y': [0, height],
        'z': [-bound, bound],
    }


# ── the anchoring rule ──────────────────────────────────────────────────────

def aabb(command: dict) -> tuple[list[float], list[float]] | None:
    '''The axis-aligned box a command occupies, as (min, max) in blocks.

    Each op anchors differently, and the difference is easy to get wrong:

        box       `at` is the MINIMUM CORNER   -> at .. at + size
        sphere    `at` is the CENTRE           -> at - r .. at + r
        cylinder  `at` is the CENTRE, and the height is centred on it too
                                               -> at.y - h/2 .. at.y + h/2

    Returns None for ops that occupy nothing (clear, remove).
    '''
    op = command.get('op')
    if op == 'box':
        at, size = command['at'], command['size']
        return list(at), [at[i] + size[i] for i in range(3)]
    if op == 'sphere':
        at, r = command['at'], command['r']
        return [at[i] - r for i in range(3)], [at[i] + r for i in range(3)]
    if op == 'cylinder':
        at, r, h = command['at'], command['r'], command['h']
        return ([at[0] - r, at[1] - h / 2, at[2] - r],
                [at[0] + r, at[1] + h / 2, at[2] + r])
    return None


def out_of_bounds(command: dict, bounds: dict) -> list[str]:
    '''Which axes a command leaves the world on. Empty means it fits.

    The server is still the authority — this only fails earlier, with a message
    that names the axis and the offending value.
    '''
    box = aabb(command)
    if box is None:
        return []

    low, high = box
    problems = []
    for index, axis in enumerate('xyz'):
        floor, ceiling = bounds[axis]
        if low[index] < floor:
            problems.append(f'{axis}={low[index]:g} is below the world floor {floor:g}')
        if high[index] > ceiling:
            problems.append(f'{axis}={high[index]:g} is past the world edge {ceiling:g}')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Digest the server's published contract: ops, materials by family, bounds.",
    )
    parser.add_argument('--bin', help='path to the codeblox binary')
    parser.add_argument('--refresh', action='store_true',
                        help='re-fetch instead of using the cached contract')
    parser.add_argument('--json', action='store_true', help='emit the digest as JSON')
    parser.add_argument('--raw', action='store_true', help='emit the contract unreduced')
    args = parser.parse_args(argv)

    try:
        binary = rc.resolve(args.bin, os.environ.copy(), Path.cwd())['path']
        contract = fetch(binary, args.refresh)
    except (rc.ResolutionError, WorldError) as exc:
        print(f'world: {exc}', file=sys.stderr)
        return EXIT_USAGE if isinstance(exc, rc.ResolutionError) else EXIT_NETWORK

    payload = contract if args.raw else digest(contract)
    if args.json or args.raw:
        print(json.dumps(payload))
    else:
        print(render(payload))
    return EXIT_OK


def render(view: dict) -> str:
    '''A compact human/agent-readable digest.'''
    bounds = view['bounds']
    lines = [
        f"block {view['blockLabel']} ({view['blockSize']} m)   "
        f"world {view['extentMetres']} m half-extent",
        f"bounds  x {bounds['x'][0]}..{bounds['x'][1]}   "
        f"y {bounds['y'][0]}..{bounds['y'][1]}   z {bounds['z'][0]}..{bounds['z'][1]}  (blocks)",
        f"ops     {', '.join(sorted(view['ops']))}",
        f"materials {view['materialCount']} in {len(view['families'])} families:",
    ]
    for family, names in sorted(view['families'].items()):
        lines.append(f"  {family:<9} {len(names):>3}  {', '.join(names[:8])}"
                     + ('  …' if len(names) > 8 else ''))
    return '\n'.join(lines)


if __name__ == '__main__':
    sys.exit(main())
