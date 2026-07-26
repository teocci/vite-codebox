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


# ── wheel ───────────────────────────────────────────────────────────────────

def test_a_wheel_is_one_tube_about_the_named_axis():
    # The case the native ops exist for: a wheel is a cylinder about x, which the
    # y-only `cylinder` could not express, so builds used spheres instead.
    parts = shapes.wheel((10, 8, 0), 'slate', r=8, width=4, axis='x')
    assert [p['op'] for p in parts] == ['tube']
    assert parts[0]['axis'] == 'x'
    assert (parts[0]['r'], parts[0]['h']) == (8, 4)


def test_a_wheels_width_runs_along_its_axis_and_its_diameter_across():
    low, high = occupied(shapes.wheel((0, 8, 0), 'slate', r=8, width=4, axis='x'))
    assert [high[i] - low[i] for i in range(3)] == [4, 16, 16]


def test_a_wheel_on_z_puts_its_width_on_z():
    low, high = occupied(shapes.wheel((0, 8, 0), 'slate', r=8, width=4, axis='z'))
    assert [high[i] - low[i] for i in range(3)] == [16, 16, 4]


def test_a_hub_is_a_second_part_standing_proud_of_the_tyre():
    parts = shapes.wheel((0, 8, 0), 'slate', r=8, width=4, axis='x', hub_mat='chrome')
    assert len(parts) == 2
    assert parts[1]['mat'] == 'chrome'
    assert parts[1]['r'] < parts[0]['r']
    assert parts[1]['h'] > parts[0]['h']


def test_no_hub_material_means_no_hub():
    assert len(shapes.wheel((0, 8, 0), 'slate', r=8, width=4)) == 1


def test_a_hub_as_wide_as_the_tyre_is_refused():
    # It would swallow the tyre entirely and read as a plain disc.
    with pytest.raises(shapes.ShapeError):
        shapes.wheel((0, 8, 0), 'slate', r=8, hub_mat='chrome', hub_r=8)


def test_a_wheel_needs_a_real_axis():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.wheel((0, 8, 0), 'slate', axis='w')
    assert 'axis' in str(exc.value)


def test_a_wheel_thinner_than_two_blocks_of_radius_is_refused():
    with pytest.raises(shapes.ShapeError):
        shapes.wheel((0, 8, 0), 'slate', r=1)


# ── taper ───────────────────────────────────────────────────────────────────

def test_a_taper_starts_at_its_base_footprint_and_ends_at_its_top():
    parts = shapes.taper((0, 0, 0), (8, 8, 8), 'granite', top=(2, 2), steps=4)
    first, last = parts[0], parts[-1]
    assert (first['size'][0], first['size'][2]) == (8, 8)
    assert (last['size'][0], last['size'][2]) == (2, 2)


def test_a_taper_never_widens_on_the_way_up():
    parts = shapes.taper((0, 0, 0), (12, 20, 12), 'granite', top=(2, 2), steps=6)
    widths = [p['size'][0] for p in parts]
    assert widths == sorted(widths, reverse=True)


def test_a_tapers_slabs_stack_without_a_gap():
    # A gap between slabs is a ring of daylight all the way round the spire, and
    # nothing else would report it.
    parts = shapes.taper((0, 0, 0), (8, 9, 8), 'granite', steps=4)
    for lower, upper in zip(parts, parts[1:]):
        assert lower['at'][1] + lower['size'][1] == upper['at'][1]


def test_a_taper_is_exactly_as_tall_as_it_was_asked_to_be():
    parts = shapes.taper((0, 0, 0), (8, 9, 8), 'granite', steps=4)
    low, high = occupied(parts)
    assert high[1] - low[1] == 9


def test_a_taper_stays_centred_on_its_base():
    # Within half a block: an odd footprint cannot sit centred on a half-block
    # coordinate, and rounding it is preferable to forcing the width's parity.
    parts = shapes.taper((0, 0, 0), (12, 12, 12), 'granite', top=(2, 2), steps=4)
    for part in parts:
        centre = part['at'][0] + part['size'][0] / 2
        assert abs(centre - 6) <= 0.5


def test_a_taper_defaults_to_narrowing_to_a_point():
    parts = shapes.taper((0, 0, 0), (8, 8, 8), 'granite', steps=4)
    assert (parts[-1]['size'][0], parts[-1]['size'][2]) == (1, 1)


def test_a_taper_with_more_steps_than_height_is_refused():
    # Each slab would round to zero height, which `box` would reject one layer
    # deeper with a message about a size rather than about the steps.
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.taper((0, 0, 0), (8, 3, 8), 'granite', steps=8)
    assert 'steps' in str(exc.value)


def test_a_taper_that_widens_is_refused():
    with pytest.raises(shapes.ShapeError):
        shapes.taper((0, 0, 0), (8, 8, 8), 'granite', top=(12, 12))


# ── dome ────────────────────────────────────────────────────────────────────

def test_a_dome_is_one_ellipsoid_of_twice_its_rise():
    # Composed, not carved — there is no subtraction, so the dome is a full
    # ellipsoid whose lower half is inside whatever it sits on.
    parts = shapes.dome((0, 10, 0), (20, 8, 20), 'marble')
    assert [p['op'] for p in parts] == ['ellipsoid']
    assert parts[0]['size'] == [20, 16, 20]
    assert parts[0]['at'] == [0, 10, 0]


def test_a_domes_visible_half_is_the_rise_it_was_given():
    low, high = occupied(shapes.dome((0, 10, 0), (20, 8, 20), 'marble'))
    assert high[1] - 10 == 8


def test_a_dome_that_would_bury_itself_below_the_floor_is_refused():
    # The bounds gate would catch it, but only after naming a y the caller never
    # wrote; refusing here can say which half is the problem.
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.dome((0, 4, 0), (20, 8, 20), 'marble')
    assert 'floor' in str(exc.value)


def test_a_dome_needs_a_positive_rise():
    with pytest.raises(shapes.ShapeError):
        shapes.dome((0, 10, 0), (20, 0, 20), 'marble')


# ── pane ────────────────────────────────────────────────────────────────────

def test_a_raked_pane_climbs_as_it_runs():
    # Nothing is ever rotated (`_compose` is IDENTITY_QUAT), so a leaning pane is
    # a staircase of thin slabs. This is the arithmetic behind 178 of the 305
    # parts in the Tesla's greenhouse stage.
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=4)
    assert len(parts) == 4
    alongs = [p['at'][2] for p in parts]
    heights = [p['at'][1] for p in parts]
    assert alongs == sorted(alongs) and heights == sorted(heights)
    assert alongs[0] == 0 and heights[0] == 10


def test_a_panes_slabs_leave_no_gap_along_the_run():
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=9, rise=6, steps=4)
    for lower, upper in zip(parts, parts[1:]):
        assert lower['at'][2] + lower['size'][2] == upper['at'][2]


def test_a_pane_occupies_exactly_the_envelope_it_was_given():
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8,
                        thickness=2, steps=4)
    low, high = occupied(parts)
    assert [high[i] - low[i] for i in range(3)] == [20, 8 + 2, 8]


def test_a_pane_is_only_as_thick_as_it_was_told():
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8,
                        thickness=2, steps=4)
    assert {p['size'][1] for p in parts} == {2}


def test_a_pane_can_run_along_x():
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8,
                        steps=4, axis='x')
    low, high = occupied(parts)
    assert high[0] - low[0] == 8
    assert high[2] - low[2] == 20


def test_a_frame_runs_along_both_edges_of_the_pane():
    framed = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=4,
                         frame_mat='slate_dark')
    assert {p['mat'] for p in framed} == {'glass', 'slate_dark'}
    glazed = [p for p in framed if p['mat'] == 'glass']
    assert len(glazed) == 2                          # the two steps between the caps
    for part in glazed:
        assert part['size'][0] == 18                 # inset one block on each edge


def test_a_frame_caps_the_low_and_high_ends():
    # Seen in the viewer: framing only the long edges leaves the two ends as bare
    # glass, so the frame reads as two loose rails rather than as a frame.
    framed = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=4,
                         frame_mat='slate_dark')
    caps = [p for p in framed if p['mat'] == 'slate_dark' and p['size'][0] == 20]
    assert len(caps) == 2
    lowest, highest = min(caps, key=lambda p: p['at'][1]), max(caps, key=lambda p: p['at'][1])
    assert lowest['at'][2] == 0                      # the low end of the run
    assert highest['at'][2] + highest['size'][2] == 8


def test_capping_the_ends_costs_no_extra_parts():
    # A cap replaces its step's glazing rather than sitting on top of it, which is
    # also what keeps the envelope unchanged.
    framed = shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=4,
                         frame_mat='slate_dark')
    assert len(framed) == 2 + 2 * 3                  # two caps, two glazed steps


def test_a_framed_pane_needs_a_step_for_each_cap_and_some_glazing():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=2,
                    frame_mat='slate_dark')
    assert 'steps' in str(exc.value)


def test_a_framed_pane_is_no_wider_than_an_unframed_one():
    # The frame is inset into the glazing, not bolted onto its edges, so adding
    # one cannot push the pane past the envelope the subject was measured against.
    plain = occupied(shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8, steps=4))
    framed = occupied(shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=8,
                                  steps=4, frame_mat='slate_dark'))
    assert plain == framed


def test_a_pane_with_no_rake_says_to_use_a_box():
    # Vertical or flat, a pane is one box, and a generator that emits one box is
    # a worse way to write a box.
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.pane((0, 10, 0), 'glass', width=20, run=8, rise=0)
    assert 'box' in str(exc.value)


def test_a_pane_with_more_steps_than_run_is_refused():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.pane((0, 10, 0), 'glass', width=20, run=3, rise=8, steps=8)
    assert 'steps' in str(exc.value)


def test_a_pane_defaults_to_one_step_per_block_of_rise():
    parts = shapes.pane((0, 10, 0), 'glass', width=20, run=12, rise=6)
    assert len(parts) == 6


# ── window ──────────────────────────────────────────────────────────────────

def test_a_window_composes_the_wall_around_the_opening():
    # There is no subtraction in this engine, so the hole is what is left unbuilt.
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 4, 8, 5))
    assert len(parts) == 4                       # sill, head, and two jambs
    assert all(p['op'] == 'box' for p in parts)


def test_the_opening_is_left_empty_without_a_glass_material():
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 4, 8, 5))
    assert all(p['mat'] == 'brick' for p in parts)


def test_glazing_fills_the_opening_exactly():
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 4, 8, 5),
                          glass_mat='glass_azure')
    pane_part = [p for p in parts if p['mat'] == 'glass_azure']
    assert len(pane_part) == 1
    assert pane_part[0]['at'] == [6, 4, 0]
    assert pane_part[0]['size'] == [8, 5, 2]


def test_a_door_has_no_wall_beneath_it():
    # A door is a window whose sill is the floor; a zero-height sill piece would
    # be rejected by `box` rather than simply omitted.
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 0, 8, 9))
    assert len(parts) == 3
    assert all(p['size'][1] > 0 for p in parts)


def test_an_opening_the_full_width_leaves_only_a_sill_and_a_head():
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(0, 4, 20, 5))
    assert len(parts) == 2


def test_a_window_occupies_exactly_the_panel_it_was_given():
    parts = shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 4, 8, 5),
                          glass_mat='glass_azure')
    low, high = occupied(parts)
    assert low == [0, 0, 0]
    assert [high[i] - low[i] for i in range(3)] == [20, 12, 2]


def test_a_wall_running_along_z_puts_its_opening_on_z():
    parts = shapes.window((0, 0, 0), (2, 12, 20), 'brick', hole=(6, 4, 8, 5),
                          axis='z', glass_mat='glass')
    pane_part = [p for p in parts if p['mat'] == 'glass'][0]
    assert pane_part['at'] == [0, 4, 6]
    assert pane_part['size'] == [2, 5, 8]


def test_an_opening_that_runs_off_the_wall_is_refused():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(16, 4, 8, 5))
    assert 'x' in str(exc.value)


def test_an_opening_taller_than_the_wall_is_refused():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(6, 4, 8, 20))
    assert 'y' in str(exc.value)


def test_an_opening_that_is_the_whole_wall_says_to_use_a_box():
    with pytest.raises(shapes.ShapeError) as exc:
        shapes.window((0, 0, 0), (20, 12, 2), 'brick', hole=(0, 0, 20, 12))
    assert 'box' in str(exc.value)


# ── everything lands inside the world ───────────────────────────────────────

@pytest.mark.parametrize('parts', [
    shapes.shell((0, 0, 0), (10, 8, 12), 'oak'),
    shapes.stairs((0, 0, 0), 'slate', steps=8),
    shapes.arch((0, 0, 0), 'marble', span=16, rise=6),
    shapes.bridge((0, 0, 0), 'oak', span=40, deck_height=8),
    shapes.wheel((0, 8, 0), 'slate', r=8, width=4, axis='x'),
    shapes.taper((0, 0, 0), (12, 20, 12), 'granite', top=(2, 2)),
    shapes.dome((0, 10, 0), (20, 8, 20), 'marble'),
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
