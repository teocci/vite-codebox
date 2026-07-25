'''The contract digest, and the anchoring rule the contract does not publish.

The anchoring cases are the load-bearing ones: `box` measures from its minimum
corner while `sphere` and `cylinder` measure from their centre, and a cylinder's
height is centred too. Getting that wrong places parts half a structure away, and
the server would accept it — it is valid geometry, just not what was meant.
'''

from __future__ import annotations

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


@pytest.mark.parametrize('op', ['clear', 'remove'])
def test_control_ops_occupy_nothing(op):
    assert world.aabb({'op': op, 'id': 1}) is None


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


def test_refresh_is_passed_through():
    seen = {}

    def run(argv, **_kwargs):
        seen['argv'] = argv
        return subprocess.CompletedProcess(argv, 0, json.dumps(CONTRACT), '')

    world.fetch('codeblox', refresh=True, run=run, env={})
    assert '--refresh' in seen['argv']
