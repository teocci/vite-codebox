'''Plan parsing, shape expansion, and the gate that runs before anything lands.'''

from __future__ import annotations

import io
import json
import re
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

import build
import shapes
import submit

BOUNDS = {'x': [-1600, 1600], 'y': [0, 3200], 'z': [-1600, 1600]}
EXIT_CONTRACT = submit.EXIT_CONTRACT

# Half-metre blocks: two to a metre, so a test that confuses the two gets a
# different number rather than the same one.
BLOCK = 0.5

MASS = {'shape': 'shell', 'at': [-20, 0, -20], 'size': [40, 14, 40], 'mat': 'brick'}
DETAIL = {'op': 'box', 'at': [0, 20, 0], 'size': [2, 2, 2], 'mat': 'copper'}
FAR_AWAY = {'op': 'box', 'at': [0, 3190, 0], 'size': [4, 40, 4], 'mat': 'oak'}


def plan(*stages, name='castle') -> dict:
    return {'name': name, 'stages': list(stages)}


def stage(name, *parts) -> dict:
    return {'name': name, 'parts': list(parts)}


def args(**overrides) -> Namespace:
    defaults = {'dry_run': False, 'start': None, 'only': None, 'pace': 'none',
                'no_focus': True}
    return Namespace(**{**defaults, **overrides})


def sent_batches(calls: list[list[str]]) -> int:
    '''How many real (non-dry-run) exec calls happened.'''
    return sum(1 for argv in calls if '--dry-run' not in argv)


def acking(**by_call):
    '''A `run` that answers every exec, recording the argv it was called with.'''
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        body = json.dumps({'ok': True, 'validated': 1, 'sent': 0} if '--dry-run' in argv
                          else {'ok': True, 'sent': 1, 'addedIds': [len(calls)], **by_call})
        return subprocess.CompletedProcess(argv, 0, body, '')

    return run, calls


def never(*_args, **_kwargs):
    raise AssertionError('nothing may be sent once the gate has failed')


# ── reading the plan ────────────────────────────────────────────────────────

def test_a_plan_round_trips():
    loaded = build.load_plan(io.StringIO(json.dumps(plan(stage('mass', MASS)))))
    assert loaded['name'] == 'castle'


def test_empty_stdin_says_where_the_format_is():
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO('  \n'))
    assert 'SKILL.md' in str(exc.value)


def test_malformed_json_is_reported_as_such():
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO('{"stages": ['))
    assert 'not valid JSON' in str(exc.value)


def test_a_plan_without_stages_is_refused():
    with pytest.raises(build.PlanError):
        build.load_plan(io.StringIO(json.dumps({'name': 'castle'})))


def test_a_plan_with_an_empty_stage_list_is_refused():
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps({'stages': []})))
    assert 'no stages' in str(exc.value)


def test_an_unnamed_stage_is_refused_because_failures_refer_to_the_name():
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps({'stages': [{'parts': [DETAIL]}]})))
    assert 'name' in str(exc.value)


def test_a_stage_with_no_parts_is_refused_and_named():
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps({'stages': [{'name': 'mass', 'parts': []}]})))
    assert 'mass' in str(exc.value)


# ── the subject a plan declares ─────────────────────────────────────────────

def test_a_plan_need_not_declare_a_subject():
    # Every plan predating I-8 has no subject; none of them become invalid.
    loaded = build.load_plan(io.StringIO(json.dumps(plan(stage('mass', MASS)))))
    assert loaded.get('subject') is None


def test_a_declared_subject_survives_loading():
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': [2000, 1000, 3000]}}
    loaded = build.load_plan(io.StringIO(json.dumps(body)))
    assert loaded['subject']['mm'] == [2000, 1000, 3000]


def test_a_subject_needs_all_three_axes():
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': [2000, 1000]}}
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps(body)))
    assert 'three' in str(exc.value)


def test_a_subject_axis_of_zero_is_refused():
    # It would make the ratio for that axis undefined and the gate meaningless.
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': [2000, 0, 3000]}}
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps(body)))
    assert 'positive' in str(exc.value)


def test_a_subject_measured_in_prose_is_refused():
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': ['about 2 m', 1000, 3000]}}
    with pytest.raises(build.PlanError):
        build.load_plan(io.StringIO(json.dumps(body)))


def test_a_subject_without_millimetres_says_what_it_wants():
    body = {**plan(stage('mass', MASS)), 'subject': {'name': 'a car'}}
    with pytest.raises(build.PlanError) as exc:
        build.load_plan(io.StringIO(json.dumps(body)))
    assert 'mm' in str(exc.value)


# ── the scale gate ──────────────────────────────────────────────────────────

def scaled(*sizes) -> tuple[dict, list[list[dict]]]:
    '''A one-stage plan declaring a 2x1x3 m subject, built at the given size.'''
    parts = [{'op': 'box', 'at': [0, 0, 0], 'size': list(size), 'mat': 'oak'}
             for size in sizes]
    body = {**plan(stage('mass', *parts)), 'subject': {'mm': [2000, 1000, 3000]}}
    return body, build.expand(body['stages'])


def test_the_declared_size_is_measured_in_blocks_not_metres():
    # 2x1x3 m at half-metre blocks is 4x2x6 blocks. Reading it as metres would
    # build a car the size of a house and nothing downstream would notice.
    body, batches = scaled([4, 2, 6])
    build.check_scale(body['subject'], batches, BLOCK, BOUNDS)


def test_a_build_at_the_wrong_scale_is_refused():
    body, batches = scaled([8, 4, 12])
    with pytest.raises(build.PlanError) as exc:
        build.check_scale(body['subject'], batches, BLOCK, BOUNDS)
    assert exc.value.code == EXIT_CONTRACT


def test_a_uniform_miss_is_reported_as_mechanically_repairable():
    # Every axis is out by the same factor, so one rescale fixes it.
    body, batches = scaled([8, 4, 12])
    with pytest.raises(build.PlanError) as exc:
        build.check_scale(body['subject'], batches, BLOCK, BOUNDS)
    message = str(exc.value)
    assert 'dims.py' in message and 'fit' in message
    assert '[4, 2, 6]' in message                  # what it should have been
    assert '[8, 4, 12]' in message                 # what it came out as


def test_a_proportion_error_is_not_offered_the_rescale():
    # One factor cannot fix three ratios; offering fit here would produce a
    # correctly sized wrong shape that then passes this very gate.
    body, batches = scaled([4, 8, 6])
    with pytest.raises(build.PlanError) as exc:
        build.check_scale(body['subject'], batches, BLOCK, BOUNDS)
    message = str(exc.value)
    assert 'proportion' in message
    assert 'fit' not in message


def test_one_block_of_rounding_is_not_a_scale_error():
    # to_blocks rounds to the nearest block, so a subject can be half a block
    # off through no fault of the plan.
    body, batches = scaled([5, 2, 6])
    build.check_scale(body['subject'], batches, BLOCK, BOUNDS)


def test_a_subject_too_big_for_the_world_names_what_would_fit():
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': [2_000_000, 1000, 3000]}}
    with pytest.raises(build.PlanError) as exc:
        build.check_scale(body['subject'], build.expand(body['stages']), BLOCK, BOUNDS)
    message = str(exc.value)
    assert exc.value.code == EXIT_CONTRACT
    assert 'x' in message
    assert '1600' in message                       # the largest x that fits, in metres


def test_an_oversized_subject_is_answered_with_a_bigger_world():
    # Not with a scale model: this project's worlds are configured in metres, so
    # a 2 km subject means raising world.extent, not shrinking the build.
    body = {**plan(stage('mass', MASS)), 'subject': {'mm': [2_000_000, 1000, 3000]}}
    with pytest.raises(build.PlanError) as exc:
        build.check_scale(body['subject'], build.expand(body['stages']), BLOCK, BOUNDS)
    message = str(exc.value)
    assert 'config.yaml' in message
    assert 'world.extent' in message
    assert '1000' in message                       # half-extent needed, in metres


def test_a_plan_declaring_nothing_is_not_gated_on_scale():
    build.check_scale(None, build.expand([stage('mass', MASS)]), BLOCK, BOUNDS)


def test_a_plan_with_no_geometry_is_not_gated_on_scale():
    marker = [[{'op': 'build_begin'}]]
    build.check_scale({'mm': [2000, 1000, 3000]}, marker, BLOCK, BOUNDS)


def test_the_scale_gate_runs_before_anything_is_sent():
    # The headline guarantee, again: `remove` takes an id, so there is no
    # partial undo of a wrongly-sized build.
    body, _batches = scaled([8, 4, 12])
    with pytest.raises(build.PlanError) as exc:
        build.build('codeblox', body, BOUNDS, args(), run=never, block_size=BLOCK)
    assert exc.value.code == EXIT_CONTRACT


def test_without_a_block_size_the_scale_gate_stays_out_of_the_way():
    # No contract means no way to know what a block is worth; guessing is worse
    # than not checking.
    body, _batches = scaled([8, 4, 12])
    run, _calls = acking()
    build.build('codeblox', body, BOUNDS, args(dry_run=True), run=run)


# ── expanding parts ─────────────────────────────────────────────────────────

def test_a_shape_expands_through_the_generator():
    # shell is floor + roof + four walls, and build.py must not recompute any of it.
    assert build.expand_part(MASS, 'here') == shapes.shell(
        MASS['at'], MASS['size'], MASS['mat'])


def test_a_raw_command_passes_through_untouched():
    assert build.expand_part(DETAIL, 'here') == [DETAIL]


def test_a_part_that_is_neither_shape_nor_op_is_refused():
    with pytest.raises(build.PlanError) as exc:
        build.expand_part({'at': [0, 0, 0]}, 'stage 1 (mass) part 0')
    assert 'stage 1 (mass) part 0' in str(exc.value)


def test_an_unknown_shape_lists_the_ones_that_exist():
    with pytest.raises(build.PlanError) as exc:
        build.expand_part({'shape': 'pyramid', 'mat': 'oak'}, 'here')
    message = str(exc.value)
    assert 'pyramid' in message
    assert 'shell' in message and 'bridge' in message


def test_an_unknown_key_names_what_the_generator_accepts():
    # The failure mode this replaces is a bare TypeError from **kwargs.
    with pytest.raises(build.PlanError) as exc:
        build.expand_part({'shape': 'shell', 'size': [8, 8, 8], 'mat': 'oak', 'span': 4}, 'here')
    message = str(exc.value)
    assert "'span'" in message
    assert 'thickness' in message


def test_a_hyphenated_key_is_accepted_like_its_flag():
    parts = build.expand_part(
        {'shape': 'bridge', 'at': [0, 0, 0], 'mat': 'oak', 'span': 20, 'deck-height': 4}, 'here')
    assert parts == shapes.bridge([0, 0, 0], 'oak', span=20, deck_height=4)


def test_a_missing_required_argument_names_the_stage():
    with pytest.raises(build.PlanError) as exc:
        build.expand_part({'shape': 'shell', 'mat': 'oak'}, 'stage 2 (mass) part 0')
    assert 'stage 2 (mass) part 0' in str(exc.value)


def test_impossible_geometry_is_reported_as_a_plan_error():
    with pytest.raises(build.PlanError) as exc:
        build.expand_part({'shape': 'shell', 'at': [0, 0, 0], 'size': [2, 2, 2], 'mat': 'oak'},
                          'stage 1 (mass) part 0')
    assert 'no interior' in str(exc.value)


def test_expansion_keeps_stage_order():
    batches = build.expand([stage('mass', MASS), stage('detail', DETAIL)])
    assert len(batches) == 2
    assert batches[1] == [DETAIL]


# ── the registry stays in step with shapes.py ───────────────────────────────

def test_every_generator_shapes_exposes_is_reachable_from_a_plan():
    # Adding a generator to shapes.py without registering it here would leave it
    # usable from the CLI and invisible to a plan.
    parser = shapes.build_parser()
    subcommands = {name for action in parser._actions  # noqa: SLF001
                   for name in getattr(action, 'choices', None) or []}
    assert subcommands == set(build.SHAPES)


# ── the gate ────────────────────────────────────────────────────────────────

def test_a_later_stage_out_of_bounds_sends_nothing():
    # The headline guarantee: submit.py could not see stage 2 while sending stage 1.
    stages = [stage('mass', MASS), stage('sky', FAR_AWAY)]
    with pytest.raises(build.PlanError) as exc:
        build.validate('codeblox', stages, build.expand(stages), BOUNDS, run=never)
    assert exc.value.code == EXIT_CONTRACT


def test_the_gate_names_the_stage_not_just_a_flat_command_number():
    # "command 32" across five stages is true and useless.
    stages = [stage('mass', MASS), stage('sky', FAR_AWAY)]
    with pytest.raises(build.PlanError) as exc:
        build.check_bounds(stages, build.expand(stages), BOUNDS)
    message = str(exc.value)
    assert 'stage 2 (sky)' in message
    assert 'command 0' in message
    assert 'nothing sent' in message


def test_the_whole_plan_is_validated_in_one_call():
    run, calls = acking()
    stages = [stage('mass', MASS), stage('detail', DETAIL)]
    build.validate('codeblox', stages, build.expand(stages), BOUNDS, run=run)
    assert len(calls) == 1
    assert '--dry-run' in calls[0]


def test_validation_precedes_every_real_send():
    def refuse_then_explode(argv, **_kwargs):
        assert '--dry-run' in argv, 'a real send happened before validation finished'
        return subprocess.CompletedProcess(
            argv, submit.EXIT_CONTRACT, '',
            '{"ok":false,"code":"contract_rejected","exit":5,"detail":"unknown material"}')

    with pytest.raises(submit.SubmitError):
        build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                    BOUNDS, args(), run=refuse_then_explode)


def test_a_dry_run_validates_every_stage_and_sends_nothing():
    run, calls = acking()
    report = build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                         BOUNDS, args(dry_run=True), run=run)
    assert report['sent'] == 0
    assert report['validated'] == 7          # six shell walls plus the raw box
    assert len(calls) == 1


# ── landing the stages ──────────────────────────────────────────────────────

def test_stages_are_sent_in_order_one_call_each():
    run, calls = acking()
    report = build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                         BOUNDS, args(), run=run, sleep=lambda _s: None)
    assert [('--dry-run' in c) for c in calls] == [True, False, False]
    assert [entry['name'] for entry in report['stages']] == ['mass', 'detail']


def test_from_skips_earlier_stages_but_still_validates_them():
    run, calls = acking()
    report = build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                         BOUNDS, args(start=2), run=run, sleep=lambda _s: None)
    assert [entry['name'] for entry in report['stages']] == ['detail']
    assert report['validated'] == 7          # validation still covered both stages
    assert len(calls) == 2


def test_progress_counts_against_the_plan_not_the_selection():
    # --from 2 of a 2-stage plan once reported "stage 2/1".
    seen = []
    run, _calls = acking()
    build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                BOUNDS, args(start=2), run=run, sleep=lambda _s: None,
                progress=lambda entry, total: seen.append((entry['index'], total)))
    assert seen == [(2, 2)]


def test_only_sends_the_named_stage():
    run, _calls = acking()
    report = build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                         BOUNDS, args(only='mass'), run=run, sleep=lambda _s: None)
    assert [entry['name'] for entry in report['stages']] == ['mass']


def test_only_with_no_such_stage_lists_the_names():
    with pytest.raises(build.PlanError) as exc:
        build.select([stage('mass', MASS)], None, 'roof')
    assert 'mass' in str(exc.value)


def test_from_outside_the_plan_is_refused():
    with pytest.raises(build.PlanError):
        build.select([stage('mass', MASS)], 4, None)


def test_a_failure_part_way_names_what_already_landed():
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if '--dry-run' in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"validated":7,"sent":0}', '')
        if len(calls) == 2:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"sent":6,"addedIds":[1,2,3]}', '')
        return subprocess.CompletedProcess(
            argv, submit.EXIT_SERVER, '',
            '{"ok":false,"code":"server_rejected","exit":6,"detail":"unknown material"}')

    with pytest.raises(build.PlanError) as exc:
        build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                    BOUNDS, args(), run=run, sleep=lambda _s: None)

    message = str(exc.value)
    assert exc.value.code == submit.EXIT_SERVER
    assert 'stage 1 landed' in message
    assert 'ids 1..3' in message
    assert '--from 2' in message


# ── the focus marker ────────────────────────────────────────────────────────
#
# The helper above defaults to --no-focus so the staging tests stay about
# staging. Production default is the opposite, which this pins.

def test_the_marker_is_on_by_default():
    assert build.build_parser().parse_args([]).no_focus is False


def test_the_marker_goes_out_before_the_first_stage():
    payloads = []

    def run(argv, input=None, **_kwargs):
        payloads.append((argv, input))
        body = ('{"ok":true,"validated":7,"sent":0}' if '--dry-run' in argv
                else '{"ok":true,"sent":1,"addedIds":[1]}')
        return subprocess.CompletedProcess(argv, 0, body, '')

    build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                BOUNDS, args(no_focus=False), run=run, sleep=lambda _s: None)

    real = [body for argv, body in payloads if '--dry-run' not in argv]
    assert json.loads(real[0]) == build.FOCUS_MARKER
    assert len(real) == 3          # marker, then one batch per stage


def test_the_marker_is_validated_with_the_plan():
    # An old server that does not know the op must fail here, with nothing built.
    payloads = []

    def run(argv, input=None, **_kwargs):
        payloads.append((argv, input))
        return subprocess.CompletedProcess(argv, 0, '{"ok":true,"validated":8,"sent":0}', '')

    build.validate('codeblox', [stage('detail', DETAIL)], [[DETAIL]], BOUNDS,
                   run=run, prelude=[build.FOCUS_MARKER])

    assert json.loads(payloads[0][1].splitlines()[0]) == build.FOCUS_MARKER


def test_no_focus_omits_the_marker_entirely():
    payloads = []

    def run(argv, input=None, **_kwargs):
        payloads.append(input)
        body = ('{"ok":true,"validated":1,"sent":0}' if '--dry-run' in argv
                else '{"ok":true,"sent":1,"addedIds":[1]}')
        return subprocess.CompletedProcess(argv, 0, body, '')

    build.build('codeblox', plan(stage('detail', DETAIL)), BOUNDS,
                args(no_focus=True), run=run, sleep=lambda _s: None)

    assert not any('build_begin' in (body or '') for body in payloads)


def test_a_dry_run_sends_no_marker():
    run, calls = acking()
    build.build('codeblox', plan(stage('detail', DETAIL)), BOUNDS,
                args(dry_run=True, no_focus=False), run=run)
    assert sent_batches(calls) == 0


def test_the_marker_is_not_counted_as_a_stage():
    run, _calls = acking()
    report = build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                         BOUNDS, args(no_focus=False), run=run, sleep=lambda _s: None)
    assert len(report['stages']) == 2
    assert report['validated'] == 7      # the six shell walls and the raw box
    assert [entry['index'] for entry in report['stages']] == [1, 2]


# ── pacing ──────────────────────────────────────────────────────────────────

def test_one_part_settles_in_a_single_drop():
    assert build.settle_ms(1) == build.DROP_MS


def test_a_batch_settles_after_the_last_part_has_fallen():
    assert build.settle_ms(6) == build.DROP_MS + 5 * build.STAGGER_MS


def test_settle_never_goes_negative_on_an_empty_batch():
    assert build.settle_ms(0) == build.DROP_MS


def test_pace_accepts_settle_none_and_milliseconds():
    assert build.pace_ms('none', 6) == 0
    assert build.pace_ms('settle', 6) == build.settle_ms(6)
    assert build.pace_ms('800', 6) == 800


def test_an_unparseable_pace_is_a_usage_error():
    with pytest.raises(build.PlanError) as exc:
        build.pace_ms('slowly', 1)
    assert exc.value.code == build.EXIT_USAGE


def test_the_last_stage_is_not_paced():
    waits = []
    run, _calls = acking()
    build.build('codeblox', plan(stage('mass', MASS), stage('detail', DETAIL)),
                BOUNDS, args(pace='settle'), run=run, sleep=waits.append)
    assert waits[-1] == 0
    assert waits[0] > 0


def test_the_drop_constants_still_match_the_viewer():
    '''DROP_MS and STAGGER_MS live only in DropAnimator.js and cannot be fetched.

    They are copied into build.py, so this reads the source of truth and fails
    if the copy drifts. Skipped when the engine is not alongside — the skill is
    mirrored into .agents/ and must stay runnable on its own.
    '''
    source = (Path(__file__).resolve().parents[4]
              / 'apps' / 'web' / 'src' / 'engine' / 'DropAnimator.js')
    if not source.is_file():
        pytest.skip('engine sources not alongside this copy of the skill')

    text = source.read_text(encoding='utf-8')
    found = {name: int(re.search(rf'const {name} = (\d+)', text).group(1))
             for name in ('DROP_MS', 'STAGGER_MS')}
    assert found == {'DROP_MS': build.DROP_MS, 'STAGGER_MS': build.STAGGER_MS}


# ── rendering ───────────────────────────────────────────────────────────────

def test_contiguous_ids_are_shown_as_a_range():
    assert build.id_range([7, 8, 9, 10]) == 'ids 7..10'


def test_scattered_ids_are_shown_in_full():
    assert build.id_range([7, 12]) == 'ids [7, 12]'


def test_a_clear_stage_reads_as_cleared_not_as_zero_ids():
    entry = {'index': 1, 'name': 'clear', 'count': 1, 'sent': 0,
             'addedIds': [], 'cleared': True, 'paceMs': 0}
    assert 'world cleared' in build.stage_line(entry, 5)


def test_a_progress_line_reports_the_stage_in_metres_when_it_can():
    # Blocks are the coordinate system; metres are what the subject was declared
    # in, and the only unit an operator can sanity-check a build against.
    entry = {'index': 1, 'name': 'mass', 'count': 6, 'sent': 6, 'addedIds': [1],
             'cleared': False, 'paceMs': 0, 'metres': [2.0, 1.0, 3.0]}
    assert '2×1×3 m' in build.stage_line(entry, 2)


def test_a_long_metre_label_does_not_run_into_the_pace():
    # Found live: '2.04×0.68×3.26 m' overran its column and printed as
    # '...3.26 m620ms', which reads as a single garbled number.
    entry = {'index': 4, 'name': 'wheels', 'count': 16, 'sent': 16,
             'addedIds': [11], 'cleared': False, 'paceMs': 620,
             'metres': [2.04, 0.68, 3.26]}
    line = build.stage_line(entry, 5)
    assert 'm620ms' not in line
    assert '3.26 m' in line and '620ms' in line


def test_a_world_sized_build_still_separates_its_columns():
    # The metre column yields rather than being overrun, at any magnitude.
    entry = {'index': 1, 'name': 'bridge', 'count': 900, 'sent': 900,
             'addedIds': [1], 'cleared': False, 'paceMs': 620,
             'metres': [1368.5, 1368.5, 1368.5]}
    assert 'm620ms' not in build.stage_line(entry, 2)


def test_a_progress_line_without_metres_is_unchanged():
    entry = {'index': 1, 'name': 'mass', 'count': 6, 'sent': 6, 'addedIds': [1],
             'cleared': False, 'paceMs': 0}
    assert '×' not in build.stage_line(entry, 2)


def test_a_progress_line_carries_the_stage_its_size_and_its_ids():
    entry = {'index': 2, 'name': 'mass', 'count': 6, 'sent': 6,
             'addedIds': [1, 2, 3, 4, 5, 6], 'cleared': False, 'paceMs': 440}
    line = build.stage_line(entry, 5)
    assert 'stage 2/5' in line
    assert 'mass' in line
    assert 'ids 1..6' in line
    assert '440ms' in line
