'''Every rung of the resolution ladder, plus the two ways it must refuse.'''

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import resolve_codeblox as rc


def never_found(_name, path=None):
    '''A shutil.which that finds nothing, so PATH cannot leak into a test.'''
    return None


def fake_run(returncode=0, stdout='codeblox 0.5.0\n', stderr=''):
    def run(_argv, **_kwargs):
        return subprocess.CompletedProcess(_argv, returncode, stdout, stderr)
    return run


# ── rung 1: --bin ───────────────────────────────────────────────────────────

def test_flag_wins_over_every_other_source(fake_binary, tmp_path, repo):
    named = fake_binary(name='named', directory=tmp_path / 'named')
    on_path = fake_binary(directory=tmp_path / 'onpath')
    fake_binary(directory=repo / 'clients' / 'codeblox' / 'bin')

    path, source = rc.find(str(named), {'CODEBLOX_BIN': str(on_path)}, repo,
                           which=lambda *_a, **_k: str(on_path))

    assert path == named.resolve()
    assert source == 'flag'


def test_named_but_missing_binary_is_a_hard_error(tmp_path):
    # Never fall through to another binary: running something other than what
    # the operator named is worse than failing.
    with pytest.raises(rc.ResolutionError) as exc:
        rc.find(str(tmp_path / 'nope'), {}, tmp_path, which=never_found)
    assert '--bin' in str(exc.value)
    assert 'does not exist' in str(exc.value)


@pytest.mark.skipif(os.name == 'nt', reason='os.access(X_OK) tracks the read bit on Windows')
def test_named_but_not_executable_is_a_hard_error(fake_binary, tmp_path):
    dud = fake_binary(name='dud', executable=False)
    with pytest.raises(rc.ResolutionError) as exc:
        rc.find(str(dud), {}, tmp_path, which=never_found)
    assert 'not executable' in str(exc.value)


# ── rung 2: $CODEBLOX_BIN ───────────────────────────────────────────────────

def test_env_is_used_when_no_flag_is_given(fake_binary, tmp_path):
    target = fake_binary()
    path, source = rc.find(None, {rc.ENV_BIN: str(target)}, tmp_path, which=never_found)
    assert path == target.resolve()
    assert source == 'env'


def test_env_beats_path(fake_binary, tmp_path):
    from_env = fake_binary(name='fromenv', directory=tmp_path / 'env')
    from_path = fake_binary(name='frompath', directory=tmp_path / 'path')

    path, _ = rc.find(None, {rc.ENV_BIN: str(from_env)}, tmp_path,
                      which=lambda *_a, **_k: str(from_path))
    assert path == from_env.resolve()


def test_env_pointing_nowhere_is_a_hard_error(tmp_path):
    with pytest.raises(rc.ResolutionError) as exc:
        rc.find(None, {rc.ENV_BIN: str(tmp_path / 'gone')}, tmp_path, which=never_found)
    assert rc.ENV_BIN in str(exc.value)


def test_empty_env_var_is_ignored_rather_than_fatal(fake_binary, tmp_path):
    # An exported-but-blank variable is a common shell accident; it must not
    # look like "the operator named a binary".
    on_path = fake_binary()
    path, source = rc.find(None, {rc.ENV_BIN: ''}, tmp_path,
                           which=lambda *_a, **_k: str(on_path))
    assert source == 'path'
    assert path == on_path.resolve()


# ── rung 3: $PATH ───────────────────────────────────────────────────────────

def test_path_is_used_when_nothing_is_named(fake_binary, tmp_path):
    target = fake_binary()
    path, source = rc.find(None, {'PATH': str(target.parent)}, tmp_path,
                           which=lambda *_a, **_k: str(target))
    assert path == target.resolve()
    assert source == 'path'


# ── rung 4: dev checkout ────────────────────────────────────────────────────

def test_repo_local_build_is_the_last_resort(fake_binary, repo):
    target = fake_binary(directory=repo / 'clients' / 'codeblox' / 'bin')
    path, source = rc.find(None, {}, repo, which=never_found)
    assert path == target.resolve()
    assert source == 'repo'


def test_repo_is_found_from_a_subdirectory(fake_binary, repo):
    # The agent's cwd is wherever it happens to be, not the repo root.
    target = fake_binary(directory=repo / 'clients' / 'codeblox' / 'bin')
    deep = repo / 'apps' / 'web' / 'src'
    deep.mkdir(parents=True)

    path, _ = rc.find(None, {}, deep, which=never_found)
    assert path == target.resolve()


def test_repo_without_a_built_binary_falls_through_to_the_error(repo):
    with pytest.raises(rc.ResolutionError) as exc:
        rc.find(None, {}, repo, which=never_found)
    assert rc.INSTALLER in str(exc.value)


# ── rung 5: the actionable failure ──────────────────────────────────────────

def test_nothing_found_names_every_remedy(tmp_path):
    with pytest.raises(rc.ResolutionError) as exc:
        rc.find(None, {}, tmp_path, which=never_found)

    message = str(exc.value)
    assert rc.INSTALLER in message
    assert rc.ENV_BIN in message
    assert '--bin' in message


def test_the_installer_the_error_names_actually_exists():
    '''The remedy must be runnable, not just plausible.

    This message named `npm run install:cli` for three releases. No such script
    ever existed, and nothing failed — an agent that hit exit 2 was handed a
    command that could only fail again. Naming a real path is worth nothing
    unless something checks the path is real.
    '''
    repo_root = Path(__file__).resolve().parents[4]
    assert (repo_root / rc.INSTALLER).is_file()


# ── the version gate ────────────────────────────────────────────────────────

def test_resolution_reports_the_version(fake_binary, tmp_path):
    target = fake_binary()
    found = rc.resolve(str(target), {}, tmp_path, which=never_found,
                       run=fake_run(stdout='codeblox 0.5.0\n'))
    assert found['version'] == 'codeblox 0.5.0'
    assert found['source'] == 'flag'


def test_a_binary_that_fails_version_is_rejected(fake_binary, tmp_path):
    # Present and executable is not the same as working.
    target = fake_binary()
    with pytest.raises(rc.ResolutionError) as exc:
        rc.resolve(str(target), {}, tmp_path, which=never_found,
                   run=fake_run(returncode=1, stdout='', stderr='not a codeblox build'))
    assert 'not a codeblox build' in str(exc.value)


def test_a_binary_that_hangs_is_rejected(fake_binary, tmp_path):
    def hangs(argv, **_kwargs):
        raise subprocess.TimeoutExpired(argv, rc.VERSION_TIMEOUT)

    target = fake_binary()
    with pytest.raises(rc.ResolutionError) as exc:
        rc.resolve(str(target), {}, tmp_path, which=never_found, run=hangs)
    assert 'did not answer' in str(exc.value)


# ── the CLI wrapper ─────────────────────────────────────────────────────────

def test_main_exits_usage_when_nothing_resolves(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rc.shutil, 'which', never_found)
    monkeypatch.delenv(rc.ENV_BIN, raising=False)

    assert rc.main([]) == rc.EXIT_USAGE
    assert rc.INSTALLER in capsys.readouterr().err


def test_main_prints_the_bare_path_by_default(monkeypatch, fake_binary, tmp_path, capsys):
    target = fake_binary()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rc.subprocess, 'run', fake_run())

    assert rc.main(['--bin', str(target)]) == rc.EXIT_OK
    assert capsys.readouterr().out.strip() == str(target.resolve())


def test_main_json_carries_path_source_and_version(monkeypatch, fake_binary, tmp_path, capsys):
    import json

    target = fake_binary()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rc.subprocess, 'run', fake_run(stdout='codeblox 0.5.0\n'))

    assert rc.main(['--bin', str(target), '--json']) == rc.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload == {'path': str(target.resolve()), 'source': 'flag', 'version': 'codeblox 0.5.0'}
