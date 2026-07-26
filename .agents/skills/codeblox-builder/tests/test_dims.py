'''Real dimensions to blocks, and rescaling a plan to the size it declares.'''

from __future__ import annotations

import pytest

import dims

# Half-metre blocks: two to a metre. Chosen over 1.0 so a test that silently
# treats a block as a metre gets a different number rather than the same one.
BLOCK = 0.5


def box(at, size, mat='oak') -> dict:
    return {'op': 'box', 'at': list(at), 'size': list(size), 'mat': mat}


def plan(*parts, mm=None, name='thing') -> dict:
    subject = {'mm': list(mm)} if mm else None
    body = {'name': name, 'stages': [{'name': 'mass', 'parts': list(parts)}]}
    return {**body, 'subject': subject} if subject else body


# ── conversion ──────────────────────────────────────────────────────────────

def test_a_metre_is_two_blocks_at_half_metre_blocks():
    assert dims.blocks_per_metre(BLOCK) == 2.0


def test_an_unusable_block_size_is_a_contract_error_not_a_crash():
    # The alternative is ZeroDivisionError from deep inside a conversion.
    with pytest.raises(dims.DimsError) as exc:
        dims.blocks_per_metre(0)
    assert exc.value.code == dims.EXIT_CONTRACT


def test_millimetres_become_whole_blocks_on_each_axis():
    assert dims.to_blocks([1000, 2000, 3000], BLOCK) == [2, 4, 6]


def test_a_subject_smaller_than_one_block_still_occupies_one():
    # Rounding to zero would make the axis vanish and the ratio undefined.
    assert dims.to_blocks([100, 100, 100], BLOCK) == [1, 1, 1]


def test_units_convert_through_millimetres():
    assert dims.in_mm([2], 'm') == [2000.0]
    assert dims.in_mm([1], 'in') == [25.4]


def test_an_unknown_unit_lists_the_ones_that_exist():
    with pytest.raises(dims.DimsError) as exc:
        dims.in_mm([1], 'cubits')
    assert 'mm' in str(exc.value) and 'ft' in str(exc.value)


def test_spec_sheet_order_is_transposed_into_protocol_order():
    # A spec sheet prints length, width, height; the protocol wants x, y, z.
    assert dims.from_lwh([5057, 1999, 1680]) == [1999, 1680, 5057]


# ── the plan's own extent ───────────────────────────────────────────────────

def test_the_extent_of_one_box_is_its_size():
    assert dims.extent_of([box([0, 0, 0], [4, 2, 6])]) == [4, 2, 6]


def test_the_extent_spans_every_part():
    commands = [box([0, 0, 0], [4, 2, 6]), box([10, 0, 0], [2, 2, 2])]
    assert dims.extent_of(commands) == [12, 2, 6]


def test_a_plan_of_control_ops_alone_has_no_extent():
    assert dims.extent_of([{'op': 'build_begin'}]) is None


# ── ratios ──────────────────────────────────────────────────────────────────

def test_a_uniform_miss_has_the_same_ratio_on_every_axis():
    assert dims.ratios([8, 4, 12], [4, 2, 6]) == [2.0, 2.0, 2.0]
    assert dims.spread([2.0, 2.0, 2.0]) == 0.0


def test_spread_is_measured_against_the_largest_ratio():
    assert dims.spread([1.0, 2.0, 2.0]) == 0.5


# ── fitting ─────────────────────────────────────────────────────────────────

def test_a_build_twice_its_declared_size_is_halved_to_match():
    # The whole point of fit: the built extent afterwards IS the declared size.
    subject = plan(box([0, 0, 0], [8, 4, 12]), mm=[2000, 1000, 3000])
    fitted = dims.fit(subject, BLOCK)
    assert dims.extent_of(dims.plan_commands(fitted)) == [4, 2, 6]


def test_a_build_half_its_declared_size_is_doubled_to_match():
    subject = plan(box([0, 0, 0], [2, 1, 3]), mm=[2000, 1000, 3000])
    fitted = dims.fit(subject, BLOCK)
    assert dims.extent_of(dims.plan_commands(fitted)) == [4, 2, 6]


def test_a_fitted_build_still_sits_on_the_floor():
    # Scaling about the centre would lift a grounded build off y=0 or bury it.
    subject = plan(box([0, 0, 0], [8, 4, 12]), mm=[2000, 1000, 3000])
    low, _high = dims.aabb_of(dims.plan_commands(dims.fit(subject, BLOCK)))
    assert low[1] == 0


def test_a_proportion_error_is_refused_rather_than_uniformly_scaled():
    # One factor cannot fix three ratios; scaling anyway yields a correctly
    # sized wrong shape, which is worse because it then passes the gate.
    subject = plan(box([0, 0, 0], [4, 8, 6]), mm=[2000, 1000, 3000])
    with pytest.raises(dims.DimsError) as exc:
        dims.fit(subject, BLOCK)
    message = str(exc.value)
    assert exc.value.code == dims.EXIT_CONTRACT
    assert 'proportion' in message
    assert 'y' in message                      # the outlier axis is named


def test_fitting_a_plan_that_declares_nothing_is_a_usage_error():
    with pytest.raises(dims.DimsError) as exc:
        dims.fit(plan(box([0, 0, 0], [4, 2, 6])), BLOCK)
    assert exc.value.code == dims.EXIT_USAGE
    assert 'subject' in str(exc.value)


# ── rescaling keeps the build one piece ─────────────────────────────────────

def test_two_parts_sharing_a_face_still_share_it_after_scaling():
    # Rounding `at` and `size` independently opens a one-block seam at every
    # joint. Both corners are scaled instead, and the size derived from them.
    lower = box([0, 0, 0], [7, 3, 7])
    upper = box([0, 3, 0], [7, 5, 7])           # sits exactly on `lower`
    scaled = [dims.scale_command(c, 0.5, [0, 0, 0]) for c in (lower, upper)]
    lower_top = scaled[0]['at'][1] + scaled[0]['size'][1]
    assert lower_top == scaled[1]['at'][1]


def test_a_control_op_survives_rescaling_untouched():
    marker = {'op': 'build_begin'}
    assert dims.scale_command(marker, 0.5, [0, 0, 0]) == marker


def test_no_axis_is_ever_scaled_out_of_existence():
    tiny = box([0, 0, 0], [1, 1, 1])
    scaled = dims.scale_command(tiny, 0.1, [0, 0, 0])
    assert scaled['size'] == [1, 1, 1]


# ── anchors ─────────────────────────────────────────────────────────────────

def test_the_anchors_are_the_ones_that_calibrate_everything_else():
    # Not a catalogue of objects — five human-scale references, in millimetres.
    assert dims.ANCHORS['storey'] == 3000
    assert dims.to_blocks([dims.ANCHORS['storey']] * 3, BLOCK)[0] == 6
