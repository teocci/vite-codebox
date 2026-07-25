'''Generate exact block coordinates for structures that are pure arithmetic.

    $VENV/python .../shapes.py <generator> [options] --mat NAME [--ndjson|--json]

Pipe the output straight into submit.py:

    shapes.py bridge --span 40 --mat oak | submit.py

The division of labour is the point. The model decides *what* to build — span,
proportions, materials, style — and this script computes every coordinate. Off-by-
one errors, dropped rows, and mis-centred cylinders are where a language model
reliably fails, and none of that is a judgment call, so none of it belongs in a
prompt.

Anchoring lives in world.py and is imported, never restated: `box` anchors at its
minimum corner, `sphere` and `cylinder` at their centre.
'''

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2


class ShapeError(Exception):
    '''The requested geometry is impossible, with a reason.'''


def box(at: tuple[int, int, int], size: tuple[int, int, int], mat: str) -> dict:
    '''One box command. Every generator here emits these and nothing else.'''
    w, h, d = (int(round(n)) for n in size)
    if w <= 0 or h <= 0 or d <= 0:
        raise ShapeError(f'box size must be positive, got {(w, h, d)}')
    return {'op': 'box', 'at': [int(round(n)) for n in at], 'size': [w, h, d], 'mat': mat}


# ── generators ──────────────────────────────────────────────────────────────

def shell(at, size, mat, thickness=1, open_top=False, floor=True) -> list[dict]:
    '''A hollow box: floor, optional roof, and four walls.

    Six large parts instead of a solid block, so the inside is usable. The walls
    are inset by the thickness so faces meet without overlapping.
    '''
    x, y, z = at
    w, h, d = size
    t = thickness
    if min(w, d) <= 2 * t or h <= (2 * t if not open_top else t):
        raise ShapeError(f'shell {size} is too small for thickness {t} — it would have no interior')

    parts = []
    if floor:
        parts.append(box((x, y, z), (w, t, d), mat))
    if not open_top:
        parts.append(box((x, y + h - t, z), (w, t, d), mat))

    inner_h = h - (t if floor else 0) - (0 if open_top else t)
    wall_y = y + (t if floor else 0)
    parts.append(box((x, wall_y, z), (w, inner_h, t), mat))
    parts.append(box((x, wall_y, z + d - t), (w, inner_h, t), mat))
    parts.append(box((x, wall_y, z + t), (t, inner_h, d - 2 * t), mat))
    parts.append(box((x + w - t, wall_y, z + t), (t, inner_h, d - 2 * t), mat))
    return parts


def stairs(at, mat, steps=8, rise=1, run=1, width=3, axis='x', solid=False) -> list[dict]:
    '''A flight of steps climbing along one horizontal axis.

    Each tread is one box. --solid fills each step down to the base, which reads
    as a staircase built from stone rather than a floating set of treads.
    '''
    if axis not in ('x', 'z'):
        raise ShapeError(f"axis must be x or z, got {axis!r}")
    x, y, z = at

    parts = []
    for i in range(steps):
        height = (i + 1) * rise if solid else rise
        step_y = y if solid else y + i * rise
        if axis == 'x':
            parts.append(box((x + i * run, step_y, z), (run, height, width), mat))
        else:
            parts.append(box((x, step_y, z + i * run), (width, height, run), mat))
    return parts


def arch(at, mat, span=16, rise=8, thickness=1, depth=2, segments=12) -> list[dict]:
    '''A semi-elliptical arch spanning from `at` to `at + span` along x.

    Approximated by `segments` boxes placed along the curve. This is the case
    that most rewards being computed: the segment widths and the sine placement
    are exactly the arithmetic a model gets subtly wrong.
    '''
    if segments < 2:
        raise ShapeError('an arch needs at least 2 segments')
    x, y, z = at
    half_span = span / 2
    seg_w = max(1, round(span / segments))

    parts = []
    for i in range(segments):
        theta = math.pi * (i + 0.5) / segments
        centre_x = x + half_span - half_span * math.cos(theta)
        top = y + rise * math.sin(theta)
        parts.append(box((centre_x - seg_w / 2, top, z), (seg_w, thickness, depth), mat))
    return parts


def bridge(at, mat, span=40, width=6, deck_height=8, piers=2,
           pier_mat=None, rail_mat=None) -> list[dict]:
    '''A deck on piers, with optional railings — composed from the primitives.

    Kept to a handful of large parts rather than a block-by-block deck, which is
    the guidance the skill gives and the shape the engine is built for.
    '''
    x, y, z = at
    if span < 4 or width < 3:
        raise ShapeError(f'a bridge needs span >= 4 and width >= 3, got {span} x {width}')

    parts = [box((x, y + deck_height, z), (span, 1, width), mat)]

    if piers > 0 and deck_height > 0:
        pier_w, pier_d = 3, max(1, width - 2)
        spacing = (span - pier_w) / (piers + 1) if piers > 1 else (span - pier_w) / 2
        for i in range(piers):
            offset = spacing * (i + 1) if piers > 1 else spacing
            parts.append(box((x + offset, y, z + 1), (pier_w, deck_height, pier_d),
                             pier_mat or mat))

    if rail_mat:
        rail_y = y + deck_height + 1
        parts.append(box((x, rail_y, z), (span, 1, 1), rail_mat))
        parts.append(box((x, rail_y, z + width - 1), (span, 1, 1), rail_mat))
    return parts


# ── command line ────────────────────────────────────────────────────────────

def int3(value: str) -> tuple[int, int, int]:
    parts = value.split(',')
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f'want x,y,z — got {value!r}')
    try:
        return tuple(int(p.strip()) for p in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'{value!r} is not three integers') from exc


def flag_sets(parser: argparse.ArgumentParser) -> tuple[set[str], set[str]]:
    '''(value-taking flags, all flags) across the parser and every subparser.

    Subcommand options live on the subparsers, so a scan of the top level alone
    would miss --at and --size entirely.
    '''
    takes_value: set[str] = set()
    every: set[str] = set()

    def subparsers_of(action) -> list[argparse.ArgumentParser]:
        choices = getattr(action, 'choices', None)
        if isinstance(choices, dict):
            return [c for c in choices.values() if isinstance(c, argparse.ArgumentParser)]
        return []

    def walk(p: argparse.ArgumentParser) -> None:
        for action in p._actions:  # noqa: SLF001 — argparse exposes no public API for this
            every.update(action.option_strings)
            if action.option_strings and action.nargs != 0:
                takes_value.update(action.option_strings)
            for sub in subparsers_of(action):
                walk(sub)

    walk(parser)
    return takes_value, every


def glue_negative_values(argv: list[str], parser: argparse.ArgumentParser) -> list[str]:
    '''Rewrite `--at -20,0,-3` as `--at=-20,0,-3` before argparse sees it.

    argparse treats any token starting with `-` as an option unless it parses as
    a plain negative number, and `-20,0,-3` does not. Half this world has
    negative coordinates, so without this the most ordinary invocation fails with
    "expected one argument" — a trap the caller cannot see coming and would hit
    constantly. Only a token that follows a known value-taking flag and is not
    itself a known flag is glued, so nothing else changes meaning.
    '''
    known, every_flag = flag_sets(parser)

    out: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        following = argv[index + 1] if index + 1 < len(argv) else None
        if (token in known and following is not None
                and following.startswith('-') and following not in every_flag):
            out.append(f'{token}={following}')
            index += 2
            continue
        out.append(token)
        index += 1
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Generate block coordinates for repeatable structures.',
        epilog='Pipe into submit.py:  shapes.py bridge --span 40 --mat oak | submit.py',
    )
    parser.add_argument('--json', action='store_true', help='emit a JSON array (default: NDJSON)')
    sub = parser.add_subparsers(dest='generator', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--at', type=int3, default=(0, 0, 0), help='anchor as x,y,z (default 0,0,0)')
    common.add_argument('--mat', required=True, help='material name from `world.py`')

    p = sub.add_parser('shell', parents=[common], help='hollow box: floor, roof, four walls')
    p.add_argument('--size', type=int3, required=True, help='outer extent as w,h,d')
    p.add_argument('--thickness', type=int, default=1)
    p.add_argument('--open-top', action='store_true')
    p.add_argument('--no-floor', action='store_true')

    p = sub.add_parser('stairs', parents=[common], help='a flight of steps')
    p.add_argument('--steps', type=int, default=8)
    p.add_argument('--rise', type=int, default=1)
    p.add_argument('--run', type=int, default=1)
    p.add_argument('--width', type=int, default=3)
    p.add_argument('--axis', choices=('x', 'z'), default='x')
    p.add_argument('--solid', action='store_true', help='fill each step to the base')

    p = sub.add_parser('arch', parents=[common], help='a semi-elliptical arch')
    p.add_argument('--span', type=int, default=16)
    p.add_argument('--rise', type=int, default=8)
    p.add_argument('--thickness', type=int, default=1)
    p.add_argument('--depth', type=int, default=2)
    p.add_argument('--segments', type=int, default=12)

    p = sub.add_parser('bridge', parents=[common], help='deck, piers, optional railings')
    p.add_argument('--span', type=int, default=40)
    p.add_argument('--width', type=int, default=6)
    p.add_argument('--deck-height', type=int, default=8)
    p.add_argument('--piers', type=int, default=2)
    p.add_argument('--pier-mat', help='material for the piers (default: --mat)')
    p.add_argument('--rail-mat', help='add railings in this material')
    return parser


def generate(args) -> list[dict]:
    '''Dispatch to the requested generator.'''
    if args.generator == 'shell':
        return shell(args.at, args.size, args.mat, args.thickness,
                     args.open_top, floor=not args.no_floor)
    if args.generator == 'stairs':
        return stairs(args.at, args.mat, args.steps, args.rise, args.run,
                      args.width, args.axis, args.solid)
    if args.generator == 'arch':
        return arch(args.at, args.mat, args.span, args.rise, args.thickness,
                    args.depth, args.segments)
    return bridge(args.at, args.mat, args.span, args.width, args.deck_height,
                  args.piers, args.pier_mat, args.rail_mat)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(glue_negative_values(raw, parser))
    try:
        parts = generate(args)
    except ShapeError as exc:
        print(f'shapes: {exc}', file=sys.stderr)
        return EXIT_USAGE

    if args.json:
        print(json.dumps(parts))
    else:
        for part in parts:
            print(json.dumps(part))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
