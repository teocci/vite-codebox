'''Batch parsing, the bounds gate, and how a CLI failure is passed through.'''

from __future__ import annotations

import io
import json
import subprocess

import pytest

import submit
import world

BOUNDS = {'x': [-1600, 1600], 'y': [0, 3200], 'z': [-1600, 1600]}
CONTRACT = {'config': {'blockSize': 0.02, 'boundBlocks': 1600, 'heightBlocks': 3200}}
INSIDE = {'op': 'box', 'at': [0, 0, 0], 'size': [4, 4, 4], 'mat': 'oak'}
BELOW_FLOOR = {'op': 'box', 'at': [0, -10, 0], 'size': [4, 4, 4], 'mat': 'oak'}


def fake_run(returncode=0, stdout='', stderr=''):
    def run(_argv, **_kwargs):
        return subprocess.CompletedProcess(_argv, returncode, stdout, stderr)
    return run


# ── reading the batch ───────────────────────────────────────────────────────

def test_ndjson_is_read_line_by_line():
    text = '\n'.join(json.dumps(INSIDE) for _ in range(3))
    assert len(submit.read_batch(io.StringIO(text))) == 3


def test_a_json_array_is_read_too():
    assert len(submit.read_batch(io.StringIO(json.dumps([INSIDE, INSIDE])))) == 2


def test_blank_lines_are_skipped():
    text = f'{json.dumps(INSIDE)}\n\n\n{json.dumps(INSIDE)}\n'
    assert len(submit.read_batch(io.StringIO(text))) == 2


def test_empty_stdin_says_how_to_supply_commands():
    with pytest.raises(submit.SubmitError) as exc:
        submit.read_batch(io.StringIO('   \n'))
    assert 'shapes.py' in str(exc.value)


def test_a_malformed_line_is_reported_with_its_number():
    text = f'{json.dumps(INSIDE)}\nnot json\n'
    with pytest.raises(submit.SubmitError) as exc:
        submit.read_batch(io.StringIO(text))
    assert 'line 2' in str(exc.value)


# ── the bounds gate ─────────────────────────────────────────────────────────

def test_a_batch_inside_the_world_passes_the_gate():
    submit.check_bounds([INSIDE, INSIDE], BOUNDS)      # does not raise


def test_a_batch_leaving_the_world_is_refused_as_a_contract_failure():
    with pytest.raises(submit.SubmitError) as exc:
        submit.check_bounds([INSIDE, BELOW_FLOOR], BOUNDS)
    assert exc.value.code == submit.EXIT_CONTRACT


def test_the_gate_names_which_command_is_wrong():
    # "3 commands rejected" is not actionable; "command 1 (box): y=-10" is.
    with pytest.raises(submit.SubmitError) as exc:
        submit.check_bounds([INSIDE, BELOW_FLOOR], BOUNDS)
    message = str(exc.value)
    assert 'command 1' in message
    assert 'y=-10' in message
    assert 'nothing sent' in message


def test_an_op_with_no_anchoring_rule_reaches_the_caller_as_an_anchor_error():
    # world.aabb refuses to measure an op it does not know rather than reporting
    # it as occupying nothing. The gate must not swallow that.
    with pytest.raises(world.AnchorError):
        submit.check_bounds([{'op': 'torus', 'at': [0, 0, 0], 'r': 4}], BOUNDS)


def test_an_anchor_error_exits_5_not_4(monkeypatch, capsys):
    # AnchorError subclasses WorldError, so the except order in main() decides
    # this. Getting it wrong reports "the server is unreachable" for a bad plan.
    monkeypatch.setattr(submit.rc, 'resolve', lambda *_a, **_k: {'path': 'codeblox'})
    monkeypatch.setattr(submit.world, 'fetch', lambda *_a, **_k: CONTRACT)
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps({'op': 'torus', 'at': [0, 0, 0]})))

    assert submit.main([]) == submit.EXIT_CONTRACT
    assert 'torus' in capsys.readouterr().err


def test_the_gate_runs_before_anything_is_sent():
    def explode(*_a, **_k):
        raise AssertionError('nothing may be sent once the gate has failed')

    with pytest.raises(submit.SubmitError):
        submit.submit([BELOW_FLOOR], 'codeblox', BOUNDS, dry_run=False, run=explode)


# ── submitting ──────────────────────────────────────────────────────────────

def test_a_dry_run_validates_and_sends_nothing():
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '{"ok":true,"validated":1,"sent":0}', '')

    report = submit.submit([INSIDE], 'codeblox', BOUNDS, dry_run=True, run=run)

    assert report['dryRun'] is True
    assert report['sent'] == 0
    assert len(calls) == 1
    assert '--dry-run' in calls[0]


def test_a_real_submission_validates_first_then_sends():
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        body = ('{"ok":true,"validated":1,"sent":0}' if '--dry-run' in argv
                else '{"ok":true,"sent":1,"addedIds":[7]}')
        return subprocess.CompletedProcess(argv, 0, body, '')

    report = submit.submit([INSIDE], 'codeblox', BOUNDS, dry_run=False, run=run)

    assert [('--dry-run' in c) for c in calls] == [True, False]
    assert report['addedIds'] == [7]
    assert report['sent'] == 1


def test_a_validation_failure_stops_before_the_real_send():
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv, submit.EXIT_CONTRACT, '',
            '{"ok":false,"code":"contract_rejected","exit":5,"detail":"unknown material"}')

    with pytest.raises(submit.SubmitError) as exc:
        submit.submit([INSIDE], 'codeblox', BOUNDS, dry_run=False, run=run)

    assert exc.value.code == submit.EXIT_CONTRACT
    assert len(calls) == 1


# ── passing the CLI's failure through ───────────────────────────────────────

def test_the_json_envelope_detail_is_surfaced():
    done = subprocess.CompletedProcess(
        [], 6, '', '{"ok":false,"code":"server_rejected","exit":6,"detail":"out of world bounds"}')
    assert submit.failure_detail(done) == 'out of world bounds'


def test_prose_failures_still_come_through():
    done = subprocess.CompletedProcess([], 2, '', 'codeblox: exec: unexpected argument')
    assert 'unexpected argument' in submit.failure_detail(done)


def test_the_clis_exit_code_is_preserved_not_flattened():
    # A server rejection must stay a 6 so the caller can tell it from a 5.
    with pytest.raises(submit.SubmitError) as exc:
        submit.run_exec('codeblox', [INSIDE], dry_run=False,
                        run=fake_run(submit.EXIT_SERVER, '', 'out of bounds'))
    assert exc.value.code == submit.EXIT_SERVER


def test_non_json_output_from_a_successful_call_is_reported():
    with pytest.raises(submit.SubmitError) as exc:
        submit.run_exec('codeblox', [INSIDE], dry_run=False,
                        run=fake_run(0, 'sent 1 command(s)'))
    assert 'did not emit JSON' in str(exc.value)
