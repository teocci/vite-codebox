'''INCOMPLETE — WORK IN PROGRESS, NOT WIRED UP, NEVER RUN.

    This file was written part-way through P-9 (I-8) and the session stopped
    before any of it was executed or tested. Do not trust it and do not import
    it. Nothing references it today; build.py has no scale gate yet.

    Known defect: the `factor` expression in fit() is a mangled harmonic mean
    written as a chained `and`, and is wrong. It should be the reciprocal of the
    mean of `got`. There are almost certainly others — no test has ever run.

    Outstanding for P-9, none of it done:
      - tests/test_dims.py does not exist
      - build.py: subject validation in load_plan, plan_aabb(), check_scale(),
        the two failure envelopes, metres in stage_line()
      - world.py: blocksPerMetre in digest() and the derived line in render()
      - doctor.py: carry the metre label it drops
      - builds/*.json: subject headers

    See docs/improvements/I-8.md and the approved plan for the intended design.

Turn real-world dimensions into blocks, and rescale a plan that missed.

    $VENV/python .../dims.py to-blocks 5057 1999 1680 [--mm|--m|--ft|--in] [--lwh]
    $VENV/python .../dims.py fit < builds/thing.json > builds/thing.fixed.json
    $VENV/python .../dims.py anchors

The conversion itself is one division, which is exactly why it belongs in a
script: the failure is never the arithmetic, it is forgetting that a block is not
a metre. A plan declares its subject's real size in millimetres and build.py
checks the built extent against it; this script is how that declaration gets
turned into coordinates in the first place, and how a plan that came out the
wrong size gets repaired without being rewritten by hand.

Nothing here hard-codes the block size. It comes from the server's contract via
world.py, so changing config.yaml changes the answer with no edit here.
'''

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_codeblox as rc  # noqa: E402
import world  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NETWORK = 4
EXIT_CONTRACT = 5

# Millimetres per unit, for --m/--ft/--in. Everything converges on mm because a
# block is a whole number of them at any sane block size, so the conversion to
# blocks is exact integer arithmetic rather than a float that rounds two ways.
UNITS = {'mm': 1.0, 'm': 1000.0, 'ft': 304.8, 'in': 25.4}

# Human-scale references, in mm. Not a catalogue of objects — that would be
# unbounded and would go stale. These five are here because they calibrate
# everything else: a model that knows a storey is 3 m can size a building it has
# never seen. Machine-readable and on demand, so they cost nothing until asked.
ANCHORS = {
    'person': 1750,
    'door': 2030,
    'storey': 3000,
    'lane': 3500,
    'step_riser': 180,
}

# Above this spread between the largest and smallest per-axis ratio, a build is
# the wrong *shape*, not the wrong size, and scaling it uniformly would only
# produce a correctly-sized wrong shape.
PROPORTION_TOLERANCE = 0.15


class DimsError(Exception):
    '''A conversion or rescale that cannot be done, with an exit code.'''

    def __init__(self, message: str, code: int = EXIT_USAGE):
        super().__init__(message)
        self.code = code


# ── conversion ──────────────────────────────────────────────────────────────

def blocks_per_metre(block_size: float) -> float:
    '''How many blocks span a metre. Derived, never written down.'''
    if not block_size or block_size <= 0:
        raise DimsError(f'contract reports an unusable blockSize: {block_size!r}', EXIT_CONTRACT)
    return 1.0 / block_size


def to_blocks(mm: list[float], block_size: float) -> list[int]:
    '''Millimetres to whole blocks on each axis, rounded to nearest.'''
    per_mm = 1.0 / (block_size * 1000.0)
    return [max(1, round(v * per_mm)) for v in mm]


def in_mm(values: list[float], unit: str) -> list[float]:
    if unit not in UNITS:
        raise DimsError(f'unknown unit {unit!r}; have {", ".join(UNITS)}')
    return [v * UNITS[unit] for v in values]


def from_lwh(values: list[float]) -> list[float]:
    '''Spec-sheet length/width/height to the protocol's x, y, z.

    Every `at` and `size` in the protocol is x, y, z — width, height, depth. A
    spec sheet prints length first and height last. Transposing those is the
    single most likely way to declare a subject wrong, and it fails quietly
    because the numbers are all plausible, so it gets a flag rather than a
    warning in prose.
    '''
    length, width, height = values
    return [width, height, length]


# ── the plan's own extent ───────────────────────────────────────────────────

def plan_commands(plan: dict) -> list[dict]:
    '''Every part command a plan expands to, flattened across its stages.

    Imported from build.py rather than reimplemented: the shape generators and
    their argument binding are build.py's, and a second copy here would drift.
    '''
    import build  # local: build imports world too, and this avoids a cycle at import time
    return [command for batch in build.expand(plan['stages']) for command in batch]


def aabb_of(commands: list[dict]) -> tuple[list[float], list[float]] | None:
    '''The union AABB of a command list, in blocks, or None if it has no geometry.'''
    boxes = [box for box in (world.aabb(command) for command in commands) if box is not None]
    if not boxes:
        return None
    low = [min(box[0][i] for box in boxes) for i in range(3)]
    high = [max(box[1][i] for box in boxes) for i in range(3)]
    return low, high


def extent_of(commands: list[dict]) -> list[float] | None:
    box = aabb_of(commands)
    return None if box is None else [box[1][i] - box[0][i] for i in range(3)]


# ── rescaling ───────────────────────────────────────────────────────────────

def ratios(actual: list[float], expected: list[int]) -> list[float]:
    return [(actual[i] / expected[i]) if expected[i] else 0.0 for i in range(3)]


def spread(values: list[float]) -> float:
    '''How far apart the per-axis ratios are, relative to the largest.'''
    hi, lo = max(values), min(values)
    return 0.0 if hi == 0 else (hi - lo) / hi


def scale_command(command: dict, factor: float, about: list[float]) -> dict:
    '''One command scaled about a point, in block space.

    Both corners are scaled and the size derived as `max - min`, never `at` and
    `size` independently. Rounding them separately is what opens a one-block seam
    at every joint: two parts that shared a face in the plan stop sharing one in
    the world, and the gap is a whole block wide.
    '''
    box = world.aabb(command)
    if box is None:
        return dict(command)

    low, high = box
    new_low = [round(about[i] + (low[i] - about[i]) * factor) for i in range(3)]
    new_high = [round(about[i] + (high[i] - about[i]) * factor) for i in range(3)]
    size = [max(1, new_high[i] - new_low[i]) for i in range(3)]
    centre = [new_low[i] + size[i] / 2 for i in range(3)]

    out = dict(command)
    op = command['op']
    if op == 'box':
        out['at'], out['size'] = new_low, size
    elif op == 'fill':
        out['from'] = new_low
        out['to'] = [new_low[i] + size[i] - 1 for i in range(3)]
    elif op == 'sphere':
        out['at'] = [round(c) for c in centre]
        out['r'] = max(1, round(max(size) / 2))
    elif op == 'ellipsoid':
        out['at'], out['size'] = [round(c) for c in centre], size
    elif op in ('cylinder', 'tube'):
        axis = world.AXES.index(command.get('axis', 'y'))
        radial = [size[i] for i in range(3) if i != axis]
        out['at'] = [round(c) for c in centre]
        out['r'] = max(1, round(max(radial) / 2))
        out['h'] = max(1, size[axis])
    return out


def rescale(plan: dict, factor: float, about: list[float] | None = None) -> dict:
    '''A copy of the plan with every part scaled about `about`.

    Shape calls are expanded to raw commands first, because a generator's
    arguments are not uniformly lengths — `segments`, `steps` and `thickness`
    would all be scaled wrongly. The expanded plan is still a faithful record;
    it is just no longer parameterised.
    '''
    commands = plan_commands(plan)
    if about is None:
        box = aabb_of(commands)
        if box is None:
            raise DimsError('plan has no geometry to rescale', EXIT_CONTRACT)
        low, high = box
        # Grounded and centred: keep the footprint centred but leave the build
        # sitting on the floor rather than scaling its height off it.
        about = [(low[0] + high[0]) / 2, low[1], (low[2] + high[2]) / 2]

    out = dict(plan)
    out['stages'] = []
    for stage in plan['stages']:
        import build
        batch = [c for part in stage['parts']
                 for c in build.expand_part(part, f'stage {stage["name"]}')]
        out['stages'].append({
            **stage,
            'parts': [scale_command(c, factor, about) for c in batch],
        })
    return out


def fit(plan: dict, block_size: float) -> dict:
    '''Rescale a plan to the size its own subject declares.

    Refuses a non-uniform miss. A single factor cannot fix three different
    ratios, and applying one anyway produces a correctly-sized build that is
    still the wrong shape — which is worse than the original, because it now
    passes the gate.
    '''
    subject = plan.get('subject') or {}
    declared = subject.get('mm')
    if not declared:
        raise DimsError('plan has no subject.mm to fit against', EXIT_USAGE)

    expected = to_blocks(declared, block_size)
    actual = extent_of(plan_commands(plan))
    if actual is None:
        raise DimsError('plan has no geometry to measure', EXIT_CONTRACT)

    got = ratios(actual, expected)
    if spread(got) > PROPORTION_TOLERANCE:
        worst = max(range(3), key=lambda i: abs(got[i] - max(got)))
        raise DimsError(
            'this is a proportion error, not a scale error — one factor cannot fix it.\n'
            f'  expected {expected} blocks, built {[round(v) for v in actual]}\n'
            f'  per-axis ratio {[round(r, 3) for r in got]} '
            f'(spread {spread(got):.0%}, limit {PROPORTION_TOLERANCE:.0%})\n'
            f'  the {world.AXES[worst]} axis is the outlier — fix the geometry, then re-run fit',
            EXIT_CONTRACT)

    factor = sum(1 / r for r in got if r) and len([r for r in got if r]) / sum(1 / r for r in got if r)
    return rescale(plan, factor)


# ── command line ────────────────────────────────────────────────────────────

def block_size_from_contract(binary_hint: str | None) -> float:
    binary = rc.resolve(binary_hint, os.environ.copy(), Path.cwd())['path']
    config = world.fetch(binary).get('config', {})
    return config.get('blockSize')


def cmd_to_blocks(args) -> dict:
    if len(args.values) != 3:
        raise DimsError(f'to-blocks wants three numbers, got {len(args.values)}')
    values = from_lwh(args.values) if args.lwh else list(args.values)
    block_size = block_size_from_contract(args.bin)
    mm = in_mm(values, args.unit)
    return {
        'ok': True,
        'mm': [round(v, 3) for v in mm],
        'blocks': to_blocks(mm, block_size),
        'blockSize': block_size,
        'blocksPerMetre': round(blocks_per_metre(block_size), 6),
        'order': 'xyz',
    }


def cmd_fit(args) -> dict:
    plan = json.loads(sys.stdin.read())
    block_size = block_size_from_contract(args.bin)
    fitted = fit(plan, block_size)
    print(json.dumps(fitted, indent=2))
    extent = extent_of(plan_commands(fitted))
    return {'ok': True, 'fitted': plan.get('name'),
            'extentBlocks': [round(v) for v in extent] if extent else None}


def cmd_anchors(args) -> dict:
    block_size = block_size_from_contract(args.bin)
    return {
        'ok': True,
        'blocksPerMetre': round(blocks_per_metre(block_size), 6),
        'anchors': {name: {'mm': mm, 'blocks': to_blocks([mm, mm, mm], block_size)[0]}
                    for name, mm in ANCHORS.items()},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Convert real dimensions to blocks, and rescale a plan to its declared subject.',
        epilog='dims.py to-blocks 5057 1999 1680 --lwh   ·   dims.py fit < builds/car.json',
    )
    parser.add_argument('--bin', help='path to the codeblox binary')
    subs = parser.add_subparsers(dest='command', required=True)

    tb = subs.add_parser('to-blocks', help='real dimensions -> whole blocks, in xyz order')
    tb.add_argument('values', nargs='*', type=float, metavar='N')
    tb.add_argument('--unit', choices=list(UNITS), default='mm', help='input unit (default mm)')
    for unit in UNITS:
        tb.add_argument(f'--{unit}', dest='unit', action='store_const', const=unit,
                        help=f'read the values as {unit}')
    tb.add_argument('--lwh', action='store_true',
                    help='values are length,width,height (spec-sheet order) -> emits xyz')
    tb.set_defaults(run=cmd_to_blocks)

    ft = subs.add_parser('fit', help="rescale a plan on stdin to its own subject.mm")
    ft.set_defaults(run=cmd_fit)

    an = subs.add_parser('anchors', help='human-scale reference dimensions, in mm and blocks')
    an.set_defaults(run=cmd_anchors)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = args.run(args)
    except rc.ResolutionError as exc:
        print(f'dims: {exc}', file=sys.stderr)
        return EXIT_USAGE
    except world.AnchorError as exc:
        print(f'dims: {exc}', file=sys.stderr)
        return EXIT_CONTRACT
    except world.WorldError as exc:
        print(f'dims: {exc}', file=sys.stderr)
        return EXIT_NETWORK
    except DimsError as exc:
        print(f'dims: {exc}', file=sys.stderr)
        return exc.code
    except json.JSONDecodeError as exc:
        print(f'dims: plan is not valid JSON: {exc}', file=sys.stderr)
        return EXIT_USAGE

    print(json.dumps(report), file=sys.stderr if args.command == 'fit' else sys.stdout)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
