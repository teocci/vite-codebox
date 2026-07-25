'''Shared test setup for codeblox-builder.

Puts the skill's ``scripts/`` dir on ``sys.path`` so tests import the modules
directly, without installing a package — the same arrangement the dev-phase
family uses.
'''

import os
import stat
import sys
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SKILL / 'scripts'))


@pytest.fixture
def fake_binary(tmp_path):
    '''Create an executable stand-in for the codeblox binary.

    Returns a factory so a test can make several — a named one, one on PATH,
    one in a repo checkout — and tell them apart.
    '''
    def make(name='codeblox', directory=None, executable=True):
        target = Path(directory) if directory else tmp_path
        target.mkdir(parents=True, exist_ok=True)
        path = target / (name + '.exe' if os.name == 'nt' else name)
        path.write_text('#!/bin/sh\necho "codeblox 0.0.0-fake"\n', encoding='utf-8')
        if executable:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        else:
            # Strip every execute bit so the "named but not runnable" rung is
            # reachable. On Windows os.access(X_OK) tracks the read bit, so this
            # case is only meaningful on POSIX; tests skip it there.
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return path
    return make


@pytest.fixture
def repo(tmp_path):
    '''A directory tree that looks like a codeblox checkout.'''
    root = tmp_path / 'checkout'
    (root / 'clients' / 'codeblox' / 'bin').mkdir(parents=True)
    return root
