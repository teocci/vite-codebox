'''Generators produce exact coordinates — this is what replaces model arithmetic.

Each generator is checked against hand-computed expectations rather than against
itself, so a refactor that changes the geometry fails here.
'''

from __future__ import annotations

import pytest

import shapes
import world

BOUNDS = {'x': [-1600, 1600], 'y': [0, 3200], 'z': [-1600, 1600]}


def occupied(parts):
    '''The union AABB of a set of parts, via the shared anchoring rule.'''
    boxes = [world.aabb(p) for p in parts]
    lows = [b[0] for b in boxes]
    highs = [b[1] for b in boxes]
    return ([min(l[i] for l in lows) for i in range(3)],
            [max(h[i] for h in highs) for i in range(3)])


# ── the primitive ───────────────────────────────────────────────────────────

def test_box_rejects_a_zero_dimension():
    with pytest.raises(shapes.ShapeError):
        shapes.box((0, 0, 0), (4, 0, 4), 'oak')


def test_box_rounds_to_whole_blocks():
    part = shapes.box((0.4, 1.6, 0), (2.5, 1, 1), 'oak')
    assert part['at'] == [0, 2, 0]
    assert all(isinstance(n, int) for n in part['size'])


# ── shell ───────────────────────────────────────────────────────────────────

def test_shell_is_hollow_and_closed():
    parts = shapes.shell((0, 0, 0), (10, 8, 12), 'oak')
    assert len(parts) == 6                       # floor, roof, four walls
    low, high = occupied(parts)
    assert low == [0, 0, 0] and high == [10, 8, 12]


def test_shell_can_be_left_open_at_the_top():
    parts = shapes.shell((0, 0, 0), (10, 8, 12), 'oak', open_top=True)
    assert len(parts) == 5


def test_shell_walls_do_not_overlap_the_corners_twice():
    # The z-walls span the full width; the x-walls are inset between them, so no
    # corner is described by two parts.
    parts = shapes.shell((0, 0, 0), (10, 8, 12), 'oak', thickness=1)
    x_walls = [p for p in parts if p['size'][0] == 1]
    assert all(p['size'][2] == 10 for p in x_walls)   # 12 - 2*1


def test_shell_too_small_for_its_walls_is_refused():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.shell((0, 0, 0), (2, 8, 2), 'oak', thickness=1)
    assert 'no interior' in str(exc.value)


# ── stairs ──────────────────────────────────────────────────────────────────

def test_stairs_climb_one_rise_per_step():
    parts = shapes.stairs((0, 0, 0), 'slate', steps=4, rise=2, run=3, width=5)
    assert [p['at'] for p in parts] == [[0, 0, 0], [3, 2, 0], [6, 4, 0], [9, 6, 0]]
    assert all(p['size'] == [3, 2, 5] for p in parts)


def test_solid_stairs_fill_down_to_the_base():
    parts = shapes.stairs((0, 0, 0), 'slate', steps=3, rise=1, run=1, width=2, solid=True)
    assert all(p['at'][1] == 0 for p in parts)
    assert [p['size'][1] for p in parts] == [1, 2, 3]


def test_stairs_can_climb_along_z():
    parts = shapes.stairs((0, 0, 0), 'slate', steps=3, run=2, axis='z')
    assert [p['at'][2] for p in parts] == [0, 2, 4]
    assert all(p['at'][0] == 0 for p in parts)


def test_stairs_reject_a_vertical_axis():
    with pytest.raises(shapes.ShapeError):
        shapes.stairs((0, 0, 0), 'slate', axis='y')


# ── arch ────────────────────────────────────────────────────────────────────

def test_arch_spans_the_requested_width():
    parts = shapes.arch((0, 0, 0), 'marble', span=20, rise=8, segments=10)
    low, high = occupied(parts)
    assert low[0] >= -1 and high[0] <= 21          # within a segment's rounding
    assert len(parts) == 10


def test_arch_peaks_near_the_requested_rise():
    parts = shapes.arch((0, 0, 0), 'marble', span=20, rise=8, segments=12)
    peak = max(p['at'][1] for p in parts)
    assert 7 <= peak <= 8


def test_arch_is_symmetric_about_its_midpoint():
    parts = shapes.arch((0, 0, 0), 'marble', span=20, rise=8, segments=12)
    heights = [p['at'][1] for p in parts]
    assert heights == heights[::-1]


def test_arch_needs_at_least_two_segments():
    with pytest.raises(shapes.ShapeError):
        shapes.arch((0, 0, 0), 'marble', segments=1)


# ── bridge ──────────────────────────────────────────────────────────────────

def test_bridge_deck_sits_at_the_requested_height():
    parts = shapes.bridge((0, 0, 0), 'oak', span=40, width=6, deck_height=8, piers=0)
    deck = parts[0]
    assert deck['at'] == [0, 8, 0]
    assert deck['size'] == [40, 1, 6]


def test_bridge_piers_reach_the_deck_from_the_ground():
    parts = shapes.bridge((0, 0, 0), 'oak', span=40, deck_height=8, piers=2)
    piers = parts[1:]
    assert len(piers) == 2
    for pier in piers:
        assert pier['at'][1] == 0
        assert pier['at'][1] + pier['size'][1] == 8      # meets the deck exactly


def test_bridge_piers_are_evenly_spaced_and_inside_the_span():
    parts = shapes.bridge((0, 0, 0), 'oak', span=40, deck_height=8, piers=3)
    xs = [p['at'][0] for p in parts[1:]]
    gaps = [b - a for a, b in zip(xs, xs[1:])]

    # Spacing is (span - pier_width) / (piers + 1), which rarely divides evenly
    # into whole blocks. "Even" therefore means the gaps differ by at most one
    # block — asking for identical gaps would demand fractional positions.
    assert max(gaps) - min(gaps) <= 1
    assert all(0 <= x and x + 3 <= 40 for x in xs)        # inside the deck


def test_bridge_railings_run_along_both_edges():
    parts = shapes.bridge((0, 0, 0), 'oak', span=40, width=6, deck_height=8,
                          piers=0, rail_mat='oak_dark')
    rails = [p for p in parts if p['mat'] == 'oak_dark']
    assert len(rails) == 2
    assert {r['at'][2] for r in rails} == {0, 5}


def test_bridge_materials_can_differ_per_component():
    parts = shapes.bridge((0, 0, 0), 'oak', piers=1, pier_mat='granite', rail_mat='slate')
    assert {p['mat'] for p in parts} == {'oak', 'granite', 'slate'}


def test_an_impossibly_narrow_bridge_is_refused():
    with pytest.raises(shapes.ShapeError):
        shapes.bridge((0, 0, 0), 'oak', span=2, width=1)


# ── everything lands inside the world ───────────────────────────────────────

@pytest.mark.parametrize('parts', [
    shapes.shell((0, 0, 0), (10, 8, 12), 'oak'),
    shapes.stairs((0, 0, 0), 'slate', steps=8),
    shapes.arch((0, 0, 0), 'marble', span=16, rise=6),
    shapes.bridge((0, 0, 0), 'oak', span=40, deck_height=8),
])
def test_default_geometry_never_dips_below_the_floor(parts):
    for part in parts:
        assert world.out_of_bounds(part, BOUNDS) == []


# ── the negative-coordinate trap ────────────────────────────────────────────

def test_negative_coordinates_parse_without_the_equals_form():
    # `--at -20,0,-3` reads as an option to argparse. Half the world has negative
    # coordinates, so this would fail constantly without the glue step.
    parser = shapes.build_parser()
    argv = shapes.glue_negative_values(
        ['bridge', '--at', '-20,0,-3', '--mat', 'oak'], parser)
    args = parser.parse_args(argv)
    assert args.at == (-20, 0, -3)


def test_the_equals_form_still_works():
    parser = shapes.build_parser()
    argv = shapes.glue_negative_values(['bridge', '--at=-20,0,-3', '--mat', 'oak'], parser)
    assert parser.parse_args(argv).at == (-20, 0, -3)


def test_a_following_flag_is_never_swallowed_as_a_value():
    parser = shapes.build_parser()
    argv = shapes.glue_negative_values(
        ['bridge', '--mat', 'oak', '--json'], parser)
    assert argv == ['bridge', '--mat', 'oak', '--json']


def test_positive_coordinates_are_untouched():
    parser = shapes.build_parser()
    argv = shapes.glue_negative_values(['bridge', '--at', '1,2,3', '--mat', 'oak'], parser)
    assert argv == ['bridge', '--at', '1,2,3', '--mat', 'oak']


def test_main_emits_ndjson_by_default(capsys):
    assert shapes.main(['bridge', '--span', '12', '--mat', 'oak', '--piers', '0']) == shapes.EXIT_OK
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    import json
    assert json.loads(lines[0])['op'] == 'box'


def test_main_reports_impossible_geometry_as_usage(capsys):
    assert shapes.main(['bridge', '--span', '2', '--width', '1', '--mat', 'oak']) == shapes.EXIT_USAGE
    assert 'shapes:' in capsys.readouterr().err
