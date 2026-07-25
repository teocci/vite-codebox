'''PATH arithmetic, idempotency, and type preservation — against a fake store.

Nothing here touches the real registry. The rules being tested are the ones that
would silently corrupt an operator's PATH if they were wrong.
'''

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import install_codeblox as ic

REG_SZ = 1
REG_EXPAND_SZ = 2


class FakeEnvStore:
    '''An in-memory stand-in for HKCU\\Environment.'''

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value, kind):
        self.values[name] = (value, kind)
        self.writes.append((name, value, kind))

    def delete(self, name):
        self.values.pop(name, None)
        self.writes.append(('delete', name, None))

    @property
    def default_kind(self):
        return REG_SZ


INSTALL_DIR = Path(r'D:\apps\codeblox')


# ── appending ───────────────────────────────────────────────────────────────

def test_append_keeps_every_existing_entry():
    store = FakeEnvStore({'Path': (r'C:\a;C:\b', REG_SZ)})
    change = ic.plan_add(store, INSTALL_DIR)

    assert ic.split_path(change.after) == [r'C:\a', r'C:\b', str(INSTALL_DIR)]
    assert change.changed


def test_append_to_an_unset_path():
    store = FakeEnvStore()
    change = ic.plan_add(store, INSTALL_DIR)
    assert ic.split_path(change.after) == [str(INSTALL_DIR)]


def test_planning_alone_writes_nothing():
    # This is what makes --dry-run trustworthy.
    store = FakeEnvStore({'Path': (r'C:\a', REG_SZ)})
    ic.plan_add(store, INSTALL_DIR)
    assert store.writes == []


def test_apply_writes_once():
    store = FakeEnvStore({'Path': (r'C:\a', REG_SZ)})
    ic.plan_add(store, INSTALL_DIR).apply(store)
    assert len(store.writes) == 1


# ── idempotency ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize('existing', [
    r'C:\a;D:\apps\codeblox',
    r'C:\a;D:\APPS\CODEBLOX',      # case differs
    r'C:\a;D:\apps\codeblox\\',    # trailing separator
    r'D:\apps\codeblox;C:\a',      # already first
])
def test_reinstall_does_not_duplicate_the_entry(existing):
    store = FakeEnvStore({'Path': (existing, REG_SZ)})
    change = ic.plan_add(store, INSTALL_DIR)

    assert not change.changed
    assert change.after == existing
    change.apply(store)
    assert store.writes == []


def test_a_trailing_separator_is_preserved_not_tidied_away():
    # An empty PATH element means "the current directory" on Windows. Dropping
    # one would change lookup behaviour — this installer adds an entry and must
    # not quietly edit anything else.
    store = FakeEnvStore({'Path': (r'C:\a;C:\b;', REG_SZ)})
    change = ic.plan_add(store, INSTALL_DIR)

    assert change.after == r'C:\a;C:\b;' + str(INSTALL_DIR)
    assert change.after.startswith(r'C:\a;C:\b;')


def test_every_original_character_survives_an_append():
    original = r'C:\a;;%USERPROFILE%\bin;C:\b'
    store = FakeEnvStore({'Path': (original, REG_EXPAND_SZ)})
    change = ic.plan_add(store, INSTALL_DIR)
    assert change.after.startswith(original)


def test_removal_keeps_other_empty_entries():
    store = FakeEnvStore({'Path': (r'C:\a;;C:\b;D:\apps\codeblox', REG_SZ)})
    change = ic.plan_remove(store, INSTALL_DIR)
    assert change.after == r'C:\a;;C:\b'


# ── type preservation ───────────────────────────────────────────────────────

def test_reg_expand_sz_survives_the_write():
    # The failure this guards: writing back as REG_SZ freezes %USERPROFILE% to
    # today's expansion, so the entry stops following the variable.
    store = FakeEnvStore({'Path': (r'%USERPROFILE%\bin;C:\a', REG_EXPAND_SZ)})
    ic.plan_add(store, INSTALL_DIR).apply(store)

    value, kind = store.values['Path']
    assert kind == REG_EXPAND_SZ
    assert r'%USERPROFILE%\bin' in value


def test_reg_sz_stays_reg_sz():
    store = FakeEnvStore({'Path': (r'C:\a', REG_SZ)})
    ic.plan_add(store, INSTALL_DIR).apply(store)
    assert store.values['Path'][1] == REG_SZ


# ── removal ─────────────────────────────────────────────────────────────────

def test_uninstall_removes_only_its_own_entry():
    store = FakeEnvStore({'Path': (r'C:\a;D:\apps\codeblox;C:\b', REG_SZ)})
    change = ic.plan_remove(store, INSTALL_DIR)
    assert ic.split_path(change.after) == [r'C:\a', r'C:\b']


def test_uninstall_is_a_no_op_when_the_entry_is_absent():
    store = FakeEnvStore({'Path': (r'C:\a;C:\b', REG_SZ)})
    change = ic.plan_remove(store, INSTALL_DIR)
    assert not change.changed


def test_install_then_uninstall_restores_the_original_value():
    original = r'%USERPROFILE%\bin;C:\a;C:\b'
    store = FakeEnvStore({'Path': (original, REG_EXPAND_SZ)})

    ic.plan_add(store, INSTALL_DIR).apply(store)
    ic.plan_remove(store, INSTALL_DIR).apply(store)

    value, kind = store.values['Path']
    assert value == original
    assert kind == REG_EXPAND_SZ


# ── orchestration ───────────────────────────────────────────────────────────

def test_dry_run_reports_the_change_and_writes_nothing(tmp_path):
    store = FakeEnvStore({'Path': (r'C:\a', REG_SZ)})
    report = ic.install(INSTALL_DIR, tmp_path, store, dry_run=True, touch_path=True)

    assert report['dryRun'] is True
    assert report['pathChanged'] is True
    assert ic.split_path(report['pathAfter']) == [r'C:\a', str(INSTALL_DIR)]
    assert store.writes == []
    assert 'CODEBLOX_BIN' not in store.values


def test_dry_run_does_not_build(tmp_path):
    def explode(*_a, **_k):
        raise AssertionError('a dry run must not invoke go build')

    store = FakeEnvStore()
    ic.install(INSTALL_DIR, tmp_path, store, dry_run=True, touch_path=True, run=explode)


def test_no_path_still_sets_the_binary_variable(tmp_path, monkeypatch):
    store = FakeEnvStore({'Path': (r'C:\a', REG_SZ)})
    monkeypatch.setattr(ic, 'build', lambda *_a, **_k: tmp_path / 'codeblox')
    monkeypatch.setattr(ic, 'copy_into', lambda src, d: d / 'codeblox')
    monkeypatch.setattr(ic, 'verify', lambda *_a, **_k: 'codeblox 0.5.0')
    monkeypatch.setattr(ic, 'broadcast_change', lambda: None)

    report = ic.install(INSTALL_DIR, tmp_path, store, dry_run=False, touch_path=False)

    assert report['pathBefore'] is None
    assert store.values['Path'] == (r'C:\a', REG_SZ)   # untouched
    assert store.values['CODEBLOX_BIN'][0] == str(INSTALL_DIR / ic.binary_name())


def test_uninstall_clears_the_binary_variable(tmp_path):
    store = FakeEnvStore({
        'Path': (r'C:\a;D:\apps\codeblox', REG_SZ),
        'CODEBLOX_BIN': (r'D:\apps\codeblox\codeblox.exe', REG_SZ),
    })
    ic.uninstall(INSTALL_DIR, store, dry_run=False)

    assert 'CODEBLOX_BIN' not in store.values
    assert ic.split_path(store.values['Path'][0]) == [r'C:\a']


# ── build failures surface, they do not corrupt ─────────────────────────────

def test_a_failed_build_is_reported_with_its_output(tmp_path):
    def failing(*_a, **_k):
        return subprocess.CompletedProcess([], 1, '', 'undefined: Foo')

    with pytest.raises(ic.InstallError) as exc:
        ic.build(tmp_path, run=failing)
    assert 'undefined: Foo' in str(exc.value)


def test_missing_go_toolchain_is_explained(tmp_path):
    def no_go(*_a, **_k):
        raise FileNotFoundError('go')

    with pytest.raises(ic.InstallError) as exc:
        ic.build(tmp_path, run=no_go)
    assert 'go is not on PATH' in str(exc.value)


def test_find_repo_walks_up_from_a_subdirectory(repo):
    deep = repo / 'apps' / 'web'
    deep.mkdir(parents=True)
    assert ic.find_repo(deep) == repo


def test_find_repo_outside_a_checkout_is_explained(tmp_path):
    with pytest.raises(ic.InstallError) as exc:
        ic.find_repo(tmp_path)
    assert 'no codeblox checkout' in str(exc.value)
