'''The passthrough: what it forwards, what it returns, and how it refuses.

Every test injects both the resolver's `which` and the subprocess runner, so
nothing here needs a real binary, a server, or the ambient PATH.
'''

from __future__ import annotations

import subprocess

import cli
import resolve_codeblox as rc


def never_found(_name, path=None):
    '''A shutil.which that finds nothing, so PATH cannot leak into a test.'''
    return None


def recording_run(returncode=0):
    '''A subprocess.run that records how it was called and reports a code.'''
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode)

    run.calls = calls
    return run


# ── forwarding ──────────────────────────────────────────────────────────────

def test_argv_reaches_the_binary_verbatim(fake_binary, tmp_path):
    target = fake_binary()
    run = recording_run()

    code = cli.forward(['view', 'rotate', 'on'], {rc.ENV_BIN: str(target)}, tmp_path,
                       which=never_found, run=run)

    assert code == 0
    argv, _ = run.calls[0]
    assert argv == [str(target.resolve()), 'view', 'rotate', 'on']


def test_a_flag_is_not_swallowed_on_the_way_through(fake_binary, tmp_path):
    # This script has no flags of its own, so `--json` belongs to the CLI. I-1
    # was exactly this bug one layer down: a wrapper that parsed a flag it did
    # not own and dropped it.
    target = fake_binary()
    run = recording_run()

    cli.forward(['clear', '--json'], {rc.ENV_BIN: str(target)}, tmp_path,
                which=never_found, run=run)

    argv, _ = run.calls[0]
    assert argv[1:] == ['clear', '--json']


def test_the_exit_code_comes_back_unchanged(fake_binary, tmp_path):
    # 6 is "the server rejected it" — a caller branches on the integer, so the
    # wrapper must not flatten it to 1.
    target = fake_binary()

    code = cli.forward(['view', '99'], {rc.ENV_BIN: str(target)}, tmp_path,
                       which=never_found, run=recording_run(returncode=6))

    assert code == 6


def test_the_environment_is_passed_to_the_child(fake_binary, tmp_path):
    # CODEBLOX_TOKEN and CODEBLOX_ENDPOINT resolve inside the binary; dropping
    # the environment here would strip the credential and fail with exit 3.
    target = fake_binary()
    env = {rc.ENV_BIN: str(target), 'CODEBLOX_TOKEN': 'local-dev'}
    run = recording_run()

    cli.forward(['info'], env, tmp_path, which=never_found, run=run)

    _, kwargs = run.calls[0]
    assert kwargs['env']['CODEBLOX_TOKEN'] == 'local-dev'


def test_the_streams_are_inherited_not_captured(fake_binary, tmp_path):
    # The output is read by a person as it arrives. Capturing would buffer it
    # and merge the stdout/stderr split the CLI maintains deliberately.
    target = fake_binary()
    run = recording_run()

    cli.forward(['materials'], {rc.ENV_BIN: str(target)}, tmp_path,
                which=never_found, run=run)

    _, kwargs = run.calls[0]
    assert 'capture_output' not in kwargs
    assert 'stdout' not in kwargs


def test_the_binary_is_not_probed_for_its_version_first(fake_binary, tmp_path):
    '''`find`, not `resolve` — one subprocess per command, not two.

    `resolve` proves the file runs by calling `codeblox version`. That is worth
    a subprocess before a long build; before a single verb it doubles the cost
    to learn what the verb itself would report one line later.
    '''
    target = fake_binary()
    run = recording_run()

    cli.forward(['clear'], {rc.ENV_BIN: str(target)}, tmp_path,
                which=never_found, run=run)

    assert len(run.calls) == 1
    argv, _ = run.calls[0]
    assert 'version' not in argv


# ── the two refusals ────────────────────────────────────────────────────────

def test_no_binary_exits_usage_and_names_the_installer(tmp_path, capsys):
    code = cli.forward(['clear'], {}, tmp_path, which=never_found, run=recording_run())

    assert code == cli.EXIT_USAGE
    assert rc.INSTALLER in capsys.readouterr().err


def test_no_binary_runs_nothing(tmp_path):
    run = recording_run()
    cli.forward(['clear'], {}, tmp_path, which=never_found, run=run)
    assert run.calls == []


def test_empty_argv_is_a_usage_error(capsys):
    assert cli.main([]) == cli.EXIT_USAGE
    assert 'verb' in capsys.readouterr().err


def test_empty_argv_refuses_before_resolving(monkeypatch, tmp_path, capsys):
    # An empty invocation must not depend on a binary being present: the error
    # names the missing verb, never a missing install.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rc.shutil, 'which', never_found)
    monkeypatch.delenv(rc.ENV_BIN, raising=False)

    assert cli.main([]) == cli.EXIT_USAGE
    assert rc.INSTALLER not in capsys.readouterr().err
