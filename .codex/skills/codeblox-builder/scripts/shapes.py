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
minimum corner, `sphere`, `cylinder`, `ellipsoid` and `tube` at their centre.
'''

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import world  # noqa: E402 — for AXES, so the axis names have one definition

EXIT_OK = 0
EXIT_USAGE = 2


class ShapeError(Exception):
    '''The requested geometry is impossible, with a reason.'''


# ── the primitives generators emit ──────────────────────────────────────────

def box(at: tuple[int, int, int], size: tuple[int, int, int], mat: str) -> dict:
    '''One box command, anchored at its minimum corner.'''
    w, h, d = (int(round(n)) for n in size)
    if w <= 0 or h <= 0 or d <= 0:
        raise ShapeError(f'box size must be positive, got {(w, h, d)}')
    return {'op': 'box', 'at': [int(round(n)) for n in at], 'size': [w, h, d], 'mat': mat}


def tube(at, r, h, axis: str, mat: str) -> dict:
    '''One tube command: a cylinder about `axis`, centred on `at`.'''
    if axis not in world.AXES:
        raise ShapeError(f'axis must be one of {", ".join(world.AXES)}; got {axis!r}')
    radius, height = int(round(r)), int(round(h))
    if radius < 1 or height < 1:
        raise ShapeError(f'tube needs r >= 1 and h >= 1, got r={radius} h={height}')
    return {'op': 'tube', 'at': [int(round(n)) for n in at], 'r': radius,
            'h': height, 'axis': axis, 'mat': mat}


def ellipsoid(at, size, mat: str) -> dict:
    '''One ellipsoid command: `at` is the centre, `size` the full extent.'''
    w, h, d = (int(round(n)) for n in size)
    if w <= 0 or h <= 0 or d <= 0:
        raise ShapeError(f'ellipsoid size must be positive, got {(w, h, d)}')
    return {'op': 'ellipsoid', 'at': [int(round(n)) for n in at],
            'size': [w, h, d], 'mat': mat}


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


def wheel(at, mat, r=8, width=4, axis='x', hub_mat=None, hub_r=None) -> list[dict]:
    '''A wheel: one tube about `axis`, centred on `at`, with an optional hub.

    This is the shape the native ops were added for. A wheel is a cylinder about
    x, and `cylinder` is y-only, so before `tube` existed the only round primitive
    that could be placed here was `sphere` — which is why every vehicle and every
    animal in the build history is made of spheres.

    The hub is deliberately *proud* of the tyre on both faces rather than flush.
    Flush, it is hidden by the tyre from every angle except dead-on, and the part
    is spent for nothing.
    '''
    if axis not in world.AXES:
        raise ShapeError(f'wheel axis must be one of {", ".join(world.AXES)}; got {axis!r}')
    if r < 2:
        raise ShapeError(f'a wheel needs r >= 2 to read as round, got {r}')
    if width < 1:
        raise ShapeError(f'a wheel needs width >= 1, got {width}')

    parts = [tube(at, r, width, axis, mat)]
    if hub_mat:
        inner = max(1, round(r / 3)) if hub_r is None else hub_r
        if inner < 1 or inner >= r:
            raise ShapeError(f'hub radius {inner} must be between 1 and the tyre radius {r}')
        parts.append(tube(at, inner, width + 2, axis, hub_mat))
    return parts


def taper(at, size, mat, top=None, steps=8) -> list[dict]:
    '''A stack of slabs narrowing from a base footprint to a smaller top.

    `at` is the minimum corner and `size` is the whole envelope, w,h,d — so a
    taper occupies exactly the box it was given, which is what makes it safe to
    place against a declared subject. Spires, hulls, chimneys and ziggurats are
    all this shape, and none of them is expressible with `shell`.

    Heights are distributed by integer division rather than by rounding each
    boundary, which guarantees two properties rounding does not: no slab is zero
    blocks tall, and consecutive slabs share a face exactly. A gap between slabs
    would be a ring of daylight all the way round, and nothing downstream reports
    it.
    '''
    x, y, z = at
    w, h, d = size
    top_w, top_d = (1, 1) if top is None else top
    if steps < 2:
        raise ShapeError(f'a taper needs at least 2 steps, got {steps}')
    if w <= 0 or h <= 0 or d <= 0:
        raise ShapeError(f'taper size must be positive, got {(w, h, d)}')
    if top_w < 1 or top_d < 1:
        raise ShapeError(f'taper top must be at least 1x1, got {(top_w, top_d)}')
    if top_w > w or top_d > d:
        raise ShapeError(f'a taper narrows: top {(top_w, top_d)} is wider than '
                         f'the base {(w, d)} — swap them, or build it upside down')
    if h < steps:
        raise ShapeError(f'a taper {h} blocks tall cannot have {steps} steps — '
                         f'use at most {h}, or make it taller')

    centre_x, centre_z = x + w / 2, z + d / 2
    slab_h, extra = divmod(h, steps)
    parts = []
    level = y
    for i in range(steps):
        fraction = i / (steps - 1)
        slab_w = max(1, round(w + (top_w - w) * fraction))
        slab_d = max(1, round(d + (top_d - d) * fraction))
        height = slab_h + (1 if i < extra else 0)
        parts.append(box((centre_x - slab_w / 2, level, centre_z - slab_d / 2),
                         (slab_w, height, slab_d), mat))
        level += height
    return parts


def pane(at, mat, width=20, run=10, rise=8, thickness=1, axis='z',
         steps=None, frame_mat=None, frame=1) -> list[dict]:
    '''A raked glazed surface — a windshield, a backlight, a skylight.

    `at` is the minimum corner, the pane climbs `rise` over `run` along `axis`,
    and `width` is its extent across the other horizontal axis.

    It is a staircase of thin slabs because it has to be: `World._compose`
    composes every instance with `IDENTITY_QUAT`, so no part is ever rotated and
    a leaning surface cannot be a leaning box. That is also why this belongs in a
    script — the Tesla's greenhouse stage spent 178 of the build's 305 parts
    stepping this shape out by hand.

    A frame is inset into the glazing rather than added around it, so framing a
    pane never changes the envelope it occupies. Otherwise adding a frame would
    silently grow the build past the size its subject declares, and the scale
    gate would reject a plan for a decision that looked cosmetic.

    The frame closes all four sides: rails inset along both long edges, and the
    first and last slab given over to the frame entirely as a low and high cap.
    Capping is not optional because a half-framed pane is not a thing anyone
    wants — framing only the rails leaves both ends as bare glass, which reads as
    two loose strips rather than as a frame.
    '''
    if axis not in ('x', 'z'):
        raise ShapeError(f'a pane runs along x or z, got {axis!r}')
    if rise <= 0:
        raise ShapeError('a pane with no rise is a single flat box — write one '
                         'directly instead of stepping it')
    if width < 1 or run < 1 or thickness < 1:
        raise ShapeError(f'pane needs width, run and thickness >= 1, got '
                         f'{(width, run, thickness)}')

    count = max(1, rise) if steps is None else steps
    if count < 1:
        raise ShapeError(f'a pane needs at least 1 step, got {count}')
    if count > run:
        raise ShapeError(f'a pane running {run} blocks cannot have {count} steps — '
                         f'use at most {run}, or lengthen the run')

    x, y, z = at
    depth, extra = divmod(run, count)
    inset = frame if frame_mat else 0
    if frame_mat and 2 * inset >= width:
        raise ShapeError(f'a frame of {frame} on each edge leaves no glazing in a '
                         f'pane {width} wide')
    if frame_mat and count < 3:
        raise ShapeError(f'a framed pane needs at least 3 steps — one for each end '
                         f'cap and one to glaze — got {count} steps')

    def slab(offset_along, offset_up, span, material, across_offset=0):
        '''One slab of the stack, in the pane's own frame.'''
        if axis == 'z':
            return box((x + across_offset, offset_up, z + offset_along),
                       (span, thickness, depth_of), material)
        return box((x + offset_along, offset_up, z + across_offset),
                   (depth_of, thickness, span), material)

    parts = []
    along = 0
    for i in range(count):
        depth_of = depth + (1 if i < extra else 0)
        # The last slab's base sits at exactly y + rise, so the pane climbs the
        # rise it was given. Dividing by `count` instead would leave it short by
        # one step's worth — invisible in a screenshot, and wrong against a
        # declared subject.
        level = y + (0 if count == 1 else round(i * rise / (count - 1)))
        capping = frame_mat and i in (0, count - 1)
        if capping:
            parts.append(slab(along, level, width, frame_mat))
        else:
            parts.append(slab(along, level, width - 2 * inset, mat, across_offset=inset))
            if frame_mat:
                parts.append(slab(along, level, inset, frame_mat))
                parts.append(slab(along, level, inset, frame_mat,
                                  across_offset=width - inset))
        along += depth_of
    return parts


def window(at, size, mat, hole, axis='x', glass_mat=None) -> list[dict]:
    '''A wall panel with a rectangular opening, composed around the gap.

    `at` is the minimum corner and `size` the whole panel as w,h,d. `axis` is the
    horizontal axis the wall runs along, so the remaining horizontal axis is its
    thickness. `hole` is `(along, up, length, height)` measured from the panel's
    own minimum corner.

    Nothing is carved. There is no boolean subtraction here — `remove` deletes a
    part by id, not a region — so an opening is simply wall that was never built:
    a sill below, a head above, and a jamb either side. That is the rule SKILL.md
    states in prose, and stating it in prose is what left every wall's four
    rectangles to be worked out by hand.

    A piece that would come out zero-sized is omitted rather than emitted, which
    is what makes a door (sill on the floor) and a shopfront (opening the full
    width) the same generator as a window instead of three special cases.
    '''
    if axis not in ('x', 'z'):
        raise ShapeError(f'a wall runs along x or z, got {axis!r}')
    x, y, z = at
    w, h, d = size
    if w <= 0 or h <= 0 or d <= 0:
        raise ShapeError(f'window panel size must be positive, got {(w, h, d)}')
    along, up, length, height = hole
    run = w if axis == 'x' else d
    if length < 1 or height < 1 or along < 0 or up < 0:
        raise ShapeError(f'the opening must be at least 1x1 at a non-negative offset, '
                         f'got {hole}')
    if along + length > run:
        raise ShapeError(f'the opening runs off the wall on {axis}: {along} + {length} '
                         f'is past the panel\'s {run}')
    if up + height > h:
        raise ShapeError(f'the opening is taller than the wall on y: {up} + {height} '
                         f'is past the panel\'s {h}')
    if length == run and height == h:
        raise ShapeError('the opening is the whole panel — there is no wall left to '
                         'build; write a single box in the glazing material instead')

    thickness = d if axis == 'x' else w

    def piece(offset_along, offset_up, span, rise, material):
        '''One rectangle of the panel, in the wall's own frame.'''
        if span <= 0 or rise <= 0:
            return None
        if axis == 'x':
            return box((x + offset_along, y + offset_up, z), (span, rise, thickness), material)
        return box((x, y + offset_up, z + offset_along), (thickness, rise, span), material)

    candidates = [
        piece(0, 0, run, up, mat),                                   # sill
        piece(0, up + height, run, h - up - height, mat),             # head
        piece(0, up, along, height, mat),                             # near jamb
        piece(along + length, up, run - along - length, height, mat),  # far jamb
    ]
    if glass_mat:
        candidates.append(piece(along, up, length, height, glass_mat))
    return [part for part in candidates if part is not None]


def dome(at, size, mat) -> list[dict]:
    '''A dome sitting on `at`: one ellipsoid of twice the rise, half of it buried.

    `at` is the centre of the dome's *base* and `size` is w, rise, d — so the
    visible shape is exactly the footprint and height asked for.

    There is no boolean subtraction in this engine, so a hemisphere cannot be cut
    from a sphere. It is instead a full ellipsoid of double height whose lower
    half sits inside whatever the dome rests on, which is why the base must clear
    the rise: with nothing below, the buried half is simply below the floor. That
    is refused here rather than at the bounds gate, which would report a y the
    caller never wrote.
    '''
    x, y, z = at
    w, rise, d = size
    if w <= 0 or rise <= 0 or d <= 0:
        raise ShapeError(f'dome needs a positive footprint and rise, got {(w, rise, d)}')
    if y - rise < 0:
        raise ShapeError(f'a dome of rise {rise} based at y={y} would put its buried '
                         f'half below the floor — raise the base to at least y={rise}, '
                         f'or lower the rise to {y}')
    return [ellipsoid((x, y, z), (w, 2 * rise, d), mat)]


# ── command line ────────────────────────────────────────────────────────────

def ints(value: str, count: int, shape: str) -> tuple[int, ...]:
    parts = value.split(',')
    if len(parts) != count:
        raise argparse.ArgumentTypeError(f'want {shape} — got {value!r}')
    try:
        return tuple(int(p.strip()) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'{value!r} is not {count} integers') from exc


def int3(value: str) -> tuple[int, int, int]:
    return ints(value, 3, 'x,y,z')  # type: ignore[return-value]


def int2(value: str) -> tuple[int, int]:
    return ints(value, 2, 'w,d')  # type: ignore[return-value]


def int4(value: str) -> tuple[int, int, int, int]:
    return ints(value, 4, 'along,up,length,height')  # type: ignore[return-value]


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

    p = sub.add_parser('wheel', parents=[common], help='a tube about x, y or z, with an optional hub')
    p.add_argument('--r', type=int, default=8, help='tyre radius')
    p.add_argument('--width', type=int, default=4, help='extent along the axis')
    p.add_argument('--axis', choices=world.AXES, default='x')
    p.add_argument('--hub-mat', help='add a hub standing proud of the tyre, in this material')
    p.add_argument('--hub-r', type=int, help='hub radius (default: a third of --r)')

    p = sub.add_parser('taper', parents=[common], help='slabs narrowing from a base to a top')
    p.add_argument('--size', type=int3, required=True, help='whole envelope as w,h,d')
    p.add_argument('--top', type=int2, default=(1, 1), help='top footprint as w,d (default 1,1)')
    p.add_argument('--steps', type=int, default=8)

    p = sub.add_parser('dome', parents=[common], help='an ellipsoid dome on a base')
    p.add_argument('--size', type=int3, required=True,
                   help='footprint and visible rise as w,rise,d')

    p = sub.add_parser('pane', parents=[common],
                       help='raked glazing: a windshield, backlight or skylight')
    p.add_argument('--width', type=int, default=20, help='extent across the run')
    p.add_argument('--run', type=int, default=10, help='horizontal travel along --axis')
    p.add_argument('--rise', type=int, default=8, help='how far it climbs over the run')
    p.add_argument('--thickness', type=int, default=1)
    p.add_argument('--axis', choices=('x', 'z'), default='z')
    p.add_argument('--steps', type=int, help='slabs in the stack (default: one per block of rise)')
    p.add_argument('--frame-mat', help='inset a frame along both edges, in this material')
    p.add_argument('--frame', type=int, default=1, help='frame width on each edge')

    p = sub.add_parser('window', parents=[common],
                       help='a wall panel composed around an opening')
    p.add_argument('--size', type=int3, required=True, help='whole panel as w,h,d')
    p.add_argument('--hole', type=int4, required=True,
                   help='opening as along,up,length,height from the panel corner')
    p.add_argument('--axis', choices=('x', 'z'), default='x',
                   help='horizontal axis the wall runs along')
    p.add_argument('--glass-mat', help='fill the opening with this material')
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
    if args.generator == 'wheel':
        return wheel(args.at, args.mat, args.r, args.width, args.axis,
                     args.hub_mat, args.hub_r)
    if args.generator == 'taper':
        return taper(args.at, args.size, args.mat, args.top, args.steps)
    if args.generator == 'dome':
        return dome(args.at, args.size, args.mat)
    if args.generator == 'pane':
        return pane(args.at, args.mat, args.width, args.run, args.rise,
                    args.thickness, args.axis, args.steps, args.frame_mat, args.frame)
    if args.generator == 'window':
        return window(args.at, args.size, args.mat, args.hole, args.axis, args.glass_mat)
    if args.generator == 'bridge':
        return bridge(args.at, args.mat, args.span, args.width, args.deck_height,
                      args.piers, args.pier_mat, args.rail_mat)
    # Unreachable through argparse, which requires a known subcommand — but a
    # silent fallthrough to one particular generator is how a new subcommand ends
    # up quietly building a bridge.
    raise ShapeError(f'no generator named {args.generator!r}')


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
