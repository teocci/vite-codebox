'''Fetch the server's published contract and reduce it to a token-small digest.

    $VENV/python .claude/skills/codeblox-builder/scripts/world.py [--json] [--bin PATH]

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


class AnchorError(WorldError):
    '''A command has no anchoring rule, so its geometry cannot be measured.

    Separate from WorldError because the two mean different things to a caller:
    a failed fetch is a server problem (exit 4), while an op this module cannot
    measure is a command rejected before anything was sent (exit 5).
    '''


def fetch(binary: str, run=None, env=None) -> dict:
    '''Run `codeblox info --json` and return the parsed contract.

    `info` dials the server on every call and writes ~/.codeblox/world_info.json
    as a side effect; it never reads it. Only `codeblox materials` serves from
    that cache, which is why only `materials` carries a --refresh flag. So every
    fetch here is already live — there is no cache to bypass, and passing
    --refresh would be rejected by the verb rather than ignored.

    The practical consequence is worth stating, because getting it backwards has
    cost a misdiagnosis before: if this returns a contract that looks out of
    date, the *server* is stale, not the cache. Restart it.
    '''
    run = run or subprocess.run
    argv = [binary, 'info', '--json']
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
        'blocksPerMetre': blocks_per_metre(config.get('blockSize')),
        'bounds': bounds_of(contract),
        'extentMetres': config.get('extent'),
        'materialCount': len(palette),
        'families': families,
        'ops': {op['op']: op.get('fields', {}) for op in contract.get('ops', [])},
    }


def blocks_per_metre(block_size) -> float | None:
    '''How many blocks span a metre, or None when the contract does not say.

    Derived here rather than at each call site, because the derivation is the
    thing that gets skipped: a block is not a metre, and every place that forgets
    it produces a build off by the same factor with nothing to flag it.
    '''
    if not isinstance(block_size, (int, float)) or block_size <= 0:
        return None
    return round(1.0 / block_size, 6)


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

# Ops that carry no geometry. Listing them explicitly — rather than treating
# "not in the table below" as "occupies nothing" — is what lets aabb() raise on
# an op it does not recognise. A silent None there would let a part slip past
# both the bounds gate and the scale gate, which is exactly how `fill` used to
# escape unchecked.
CONTROL_OPS = frozenset({'remove', 'clear', 'world_info', 'build_begin'})

AXES = ('x', 'y', 'z')


def _centred(at, half: list[float]) -> tuple[list[float], list[float]]:
    '''(min, max) for a part centred on `at` with the given half-extents.'''
    return ([at[i] - half[i] for i in range(3)],
            [at[i] + half[i] for i in range(3)])


def aabb(command: dict) -> tuple[list[float], list[float]] | None:
    '''The axis-aligned box a command occupies, as (min, max) in blocks.

    Each op anchors differently, and the difference is easy to get wrong:

        box        `at` is the MINIMUM CORNER   -> at .. at + size
        fill       `from`/`to` are INCLUSIVE cells, so the extent is |to-from|+1
        sphere     `at` is the CENTRE           -> at - r .. at + r
        ellipsoid  `at` is the CENTRE, `size` is the FULL extent -> at +- size/2
        cylinder   `at` is the CENTRE, and the height is centred on it too
                                                -> at.y - h/2 .. at.y + h/2
        tube       like `cylinder`, but `h` runs along `axis` and the other two
                   axes take the diameter

    Returns None for control ops, which occupy nothing. Raises WorldError for
    anything else: an unrecognised op must fail loudly rather than be treated as
    occupying nothing, or it would bypass every geometric check downstream.
    '''
    op = command.get('op')
    if op in CONTROL_OPS:
        return None
    if op == 'box':
        at, size = command['at'], command['size']
        return list(at), [at[i] + size[i] for i in range(3)]
    if op == 'fill':
        start, end = command['from'], command['to']
        low = [min(start[i], end[i]) for i in range(3)]
        return low, [low[i] + abs(end[i] - start[i]) + 1 for i in range(3)]
    if op == 'sphere':
        r = command['r']
        return _centred(command['at'], [r, r, r])
    if op == 'ellipsoid':
        size = command['size']
        return _centred(command['at'], [size[i] / 2 for i in range(3)])
    if op == 'cylinder':
        r, h = command['r'], command['h']
        return _centred(command['at'], [r, h / 2, r])
    if op == 'tube':
        r, h, axis = command['r'], command['h'], command['axis']
        if axis not in AXES:
            raise AnchorError(f'tube axis must be one of {", ".join(AXES)}; got {axis!r}')
        half = [r, r, r]
        half[AXES.index(axis)] = h / 2
        return _centred(command['at'], half)
    raise AnchorError(
        f'no anchoring rule for op {op!r} — add one to world.aabb() before using it, '
        f'or it would bypass the bounds and scale gates')


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
    parser.add_argument('--json', action='store_true', help='emit the digest as JSON')
    parser.add_argument('--raw', action='store_true', help='emit the contract unreduced')
    args = parser.parse_args(argv)

    try:
        binary = rc.resolve(args.bin, os.environ.copy(), Path.cwd())['path']
        contract = fetch(binary)
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
    per_metre = view.get('blocksPerMetre')
    scale = f" = {per_metre:g} blocks per metre" if per_metre else ''
    lines = [
        f"block {view['blockLabel']} ({view['blockSize']} m){scale}   "
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
