'''The contract digest, and the anchoring rule the contract does not publish.

The anchoring cases are the load-bearing ones: `box` measures from its minimum
corner while `sphere` and `cylinder` measure from their centre, and a cylinder's
height is centred too. Getting that wrong places parts half a structure away, and
the server would accept it — it is valid geometry, just not what was meant.
'''

from __future__ import annotations

import inspect
import json
import subprocess

import pytest

import world

CONTRACT = {
    'config': {
        'blockSize': 0.02, 'blockLabel': '2 cm', 'extent': 32,
        'gridStep': 1, 'boundBlocks': 1600, 'heightBlocks': 3200,
    },
    'palette': {
        'oak': {'color': 1, 'family': 'opaque'},
        'granite': {'color': 2, 'family': 'opaque'},
        'glass': {'color': 3, 'family': 'glass'},
        'lantern': {'color': 4, 'family': 'emissive'},
    },
    'ops': [
        {'op': 'box', 'fields': {'at': 'int3', 'size': 'int3+', 'mat': 'material'}},
        {'op': 'sphere', 'fields': {'at': 'int3', 'r': 'int+', 'mat': 'material'}},
    ],
}

BOUNDS = world.bounds_of(CONTRACT)


# ── the digest ──────────────────────────────────────────────────────────────

def test_digest_groups_materials_by_family():
    view = world.digest(CONTRACT)
    assert view['families'] == {
        'opaque': ['granite', 'oak'],
        'glass': ['glass'],
        'emissive': ['lantern'],
    }
    assert view['materialCount'] == 4


def test_digest_keeps_the_field_types_the_server_published():
    view = world.digest(CONTRACT)
    assert view['ops']['box'] == {'at': 'int3', 'size': 'int3+', 'mat': 'material'}


def test_digest_derives_how_many_blocks_span_a_metre():
    # The one number a builder needs and the contract does not publish. Left to
    # be re-derived per call site, it gets guessed — and 1 block = 1 m is the
    # guess that produced an 80 cm castle.
    assert world.digest(CONTRACT)['blocksPerMetre'] == 50


def test_a_contract_with_no_usable_block_size_derives_nothing():
    # Reporting a number here would be inventing one.
    assert world.digest({'config': {}})['blocksPerMetre'] is None


def test_the_rendered_digest_states_the_metre_conversion():
    line = world.render(world.digest(CONTRACT)).splitlines()[0]
    assert '50' in line and 'metre' in line


def test_bounds_put_the_floor_at_zero():
    # The asymmetry that matters: x and z are symmetric about the origin, y is
    # not — nothing may be built below the floor.
    assert BOUNDS == {'x': [-1600, 1600], 'y': [0, 3200], 'z': [-1600, 1600]}


# ── anchoring ───────────────────────────────────────────────────────────────

def test_box_anchors_at_its_minimum_corner():
    low, high = world.aabb({'op': 'box', 'at': [10, 20, 30], 'size': [4, 6, 8]})
    assert low == [10, 20, 30]
    assert high == [14, 26, 38]


def test_sphere_anchors_at_its_centre():
    low, high = world.aabb({'op': 'sphere', 'at': [0, 50, 0], 'r': 5})
    assert low == [-5, 45, -5]
    assert high == [5, 55, 5]


def test_cylinder_centres_its_height_too():
    # The subtlest of the three: a box grows upward from `at`, a cylinder grows
    # in both directions from it.
    low, high = world.aabb({'op': 'cylinder', 'at': [0, 50, 0], 'r': 3, 'h': 10})
    assert low == [-3, 45, -3]
    assert high == [3, 55, 3]


def test_fill_measures_inclusive_cells():
    # from/to name cells, not corners, so a run from 0 to 3 is four blocks wide —
    # off by one in the other direction from every other op.
    low, high = world.aabb({'op': 'fill', 'from': [0, 0, 0], 'to': [3, 1, 3]})
    assert low == [0, 0, 0]
    assert high == [4, 2, 4]


def test_fill_normalises_a_reversed_range():
    low, high = world.aabb({'op': 'fill', 'from': [5, 9, 5], 'to': [2, 4, 2]})
    assert low == [2, 4, 2]
    assert high == [6, 10, 6]


def test_ellipsoid_takes_size_as_the_full_extent():
    # Unlike sphere's radius, ellipsoid's `size` is the diameter on each axis —
    # the same convention as box, but measured from the centre.
    low, high = world.aabb({'op': 'ellipsoid', 'at': [0, 50, 0], 'size': [8, 4, 12]})
    assert low == [-4, 48, -6]
    assert high == [4, 52, 6]


@pytest.mark.parametrize('axis, low, high', [
    ('x', [-20, 45, -5], [20, 55, 5]),
    ('y', [-5, 30, -5], [5, 70, 5]),
    ('z', [-5, 45, -20], [5, 55, 20]),
])
def test_tube_runs_its_height_along_the_named_axis(axis, low, high):
    # r=5, h=40: the axis takes h/2 either side, the other two take the radius.
    got_low, got_high = world.aabb(
        {'op': 'tube', 'at': [0, 50, 0], 'r': 5, 'h': 40, 'axis': axis})
    assert got_low == low
    assert got_high == high


def test_tube_rejects_an_unknown_axis():
    with pytest.raises(world.WorldError) as exc:
        world.aabb({'op': 'tube', 'at': [0, 50, 0], 'r': 5, 'h': 40, 'axis': 'w'})
    assert 'axis' in str(exc.value)


@pytest.mark.parametrize('op', sorted(world.NO_GEOMETRY_OPS))
def test_ops_without_geometry_occupy_nothing(op):
    assert world.aabb({'op': op, 'id': 1, 'n': 1, 'on': True}) is None


def test_the_two_no_geometry_sets_do_not_overlap():
    # They mirror two different sets in protocol.js. An op drifting into both
    # would still work here — the union is what aabb() reads — but it would mean
    # the mirror no longer matches the shape of what it mirrors.
    assert not (world.CONTROL_OPS & world.VIEWER_OPS)


def test_an_unknown_op_raises_rather_than_occupying_nothing():
    # The whole point of the NO_GEOMETRY_OPS allowlist: a part op with no
    # anchoring rule must fail loudly. Returning None would let it past the
    # bounds gate and out of the plan's measured extent, unseen.
    with pytest.raises(world.WorldError) as exc:
        world.aabb({'op': 'torus', 'at': [0, 0, 0], 'r': 4})
    assert 'torus' in str(exc.value)


def test_a_viewer_op_the_allowlist_has_not_learned_yet_still_raises():
    # The drift this mirror is exposed to, pinned as the behaviour it produces.
    # A sixth viewer op published by the server and not added here must raise
    # rather than measure as nothing — that raise is what makes the drift safe
    # to carry, and it is the F-2 design this phase must not weaken.
    with pytest.raises(world.AnchorError) as exc:
        world.aabb({'op': 'zoom', 'factor': 2})
    assert 'zoom' in str(exc.value)


# ── the bounds gate ─────────────────────────────────────────────────────────

def test_a_part_inside_the_world_is_accepted():
    assert world.out_of_bounds({'op': 'box', 'at': [0, 0, 0], 'size': [10, 10, 10]}, BOUNDS) == []


def test_a_box_below_the_floor_is_named_with_its_axis():
    problems = world.out_of_bounds({'op': 'box', 'at': [0, -5, 0], 'size': [2, 2, 2]}, BOUNDS)
    assert len(problems) == 1
    assert 'y=-5' in problems[0]
    assert 'floor' in problems[0]


def test_a_sphere_resting_on_the_floor_dips_below_it():
    # Centre at y=2 with r=5 puts the bottom at -3. This is exactly the mistake
    # centre-anchoring invites, and the reason the gate reports the AABB rather
    # than the anchor.
    problems = world.out_of_bounds({'op': 'sphere', 'at': [0, 2, 0], 'r': 5}, BOUNDS)
    assert problems and 'y=-3' in problems[0]


def test_a_part_past_the_edge_is_named_with_its_axis():
    problems = world.out_of_bounds({'op': 'box', 'at': [1599, 0, 0], 'size': [10, 2, 2]}, BOUNDS)
    assert any('x=1609' in p and 'edge' in p for p in problems)


def test_every_offending_axis_is_reported_not_just_the_first():
    problems = world.out_of_bounds(
        {'op': 'box', 'at': [-1605, -5, 1595], 'size': [2, 2, 20]}, BOUNDS)
    axes = {p.split('=')[0] for p in problems}
    assert axes == {'x', 'y', 'z'}


# ── fetching ────────────────────────────────────────────────────────────────

def fake_run(returncode=0, stdout='', stderr=''):
    def run(_argv, **_kwargs):
        return subprocess.CompletedProcess(_argv, returncode, stdout, stderr)
    return run


def test_fetch_parses_the_contract():
    got = world.fetch('codeblox', run=fake_run(stdout=json.dumps(CONTRACT)), env={})
    assert got['config']['boundBlocks'] == 1600


def test_fetch_surfaces_the_clis_reason():
    with pytest.raises(world.WorldError) as exc:
        world.fetch('codeblox', run=fake_run(1, stderr='not authenticated'), env={})
    assert 'not authenticated' in str(exc.value)


def test_fetch_rejects_output_that_is_not_json():
    with pytest.raises(world.WorldError) as exc:
        world.fetch('codeblox', run=fake_run(stdout='block size: 2 cm'), env={})
    assert 'did not emit JSON' in str(exc.value)


def test_fetch_offers_no_refresh_because_info_has_no_cache_to_bypass():
    # `codeblox info` dials the server on every call — contractFromCache is
    # reached only by `materials` — so there was never a cache for a refresh to
    # bypass, and --refresh was never registered on the verb.
    assert 'refresh' not in inspect.signature(world.fetch).parameters


def test_fetch_sends_only_argv_the_info_verb_accepts():
    # Asserted as equality, not membership: the test this replaces checked that
    # the mock had *received* --refresh, which stayed green for as long as the
    # flag was being sent to a verb that rejects it.
    seen = {}

    def run(argv, **_kwargs):
        seen['argv'] = argv
        return subprocess.CompletedProcess(argv, 0, json.dumps(CONTRACT), '')

    world.fetch('codeblox', run=run, env={})
    assert seen['argv'] == ['codeblox', 'info', '--json']
