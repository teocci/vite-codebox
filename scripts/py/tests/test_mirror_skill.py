'''Tests for mirror_skill.

The script deletes files, so the guard rails are what these pin. Each test
redirects ROOT/SOURCE/MIRRORS at a tmp_path tree — the real .claude/ and .codex/
are never touched.
'''

import pytest

import mirror_skill as ms


@pytest.fixture
def tree(tmp_path, monkeypatch):
    '''A miniature repo: one source skill and two mirrors, all in sync.

    Returns (source, mirrors) with the module already pointed at them.
    '''
    source = tmp_path / '.claude' / 'skills' / 'codeblox-builder'
    mirrors = [
        tmp_path / '.codex' / 'skills' / 'codeblox-builder',
        tmp_path / '.agents' / 'skills' / 'codeblox-builder',
    ]
    for root in [source, *mirrors]:
        (root / 'scripts').mkdir(parents=True)
        (root / 'SKILL.md').write_text('# skill\n', encoding='utf-8')
        (root / 'scripts' / 'world.py').write_text('X = 1\n', encoding='utf-8')

    monkeypatch.setattr(ms, 'ROOT', tmp_path)
    monkeypatch.setattr(ms, 'SOURCE', source)
    monkeypatch.setattr(ms, 'MIRRORS', mirrors)
    return source, mirrors


def test_check_passes_when_the_mirrors_match(tree):
    assert ms.main(['--check']) == ms.EXIT_OK


def test_check_reports_drift_and_writes_nothing(tree, capsys):
    source, mirrors = tree
    (mirrors[0] / 'scripts' / 'world.py').write_text('X = 2\n', encoding='utf-8')

    assert ms.main(['--check']) == ms.EXIT_DRIFT
    # --check must never repair what it found, or the next run would pass and
    # hide that a commit went out with a stale mirror.
    assert (mirrors[0] / 'scripts' / 'world.py').read_text(encoding='utf-8') == 'X = 2\n'
    assert 'scripts/world.py' in capsys.readouterr().err


def test_mirroring_writes_changed_files_and_removes_stale_ones(tree):
    source, mirrors = tree
    (source / 'SKILL.md').write_text('# changed\n', encoding='utf-8')
    orphan = mirrors[0] / 'scripts' / 'dropped.py'
    orphan.write_text('gone\n', encoding='utf-8')

    assert ms.main([]) == ms.EXIT_OK
    for mirror in mirrors:
        assert (mirror / 'SKILL.md').read_text(encoding='utf-8') == '# changed\n'
    # A file the source no longer has is drift too, not just a changed one.
    assert not orphan.exists()
    assert ms.main(['--check']) == ms.EXIT_OK


def test_an_empty_source_refuses_rather_than_emptying_both_mirrors(tree, capsys):
    source, mirrors = tree
    for path in sorted(source.rglob('*'), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()

    assert ms.main([]) == ms.EXIT_DRIFT
    assert 'refusing to mirror' in capsys.readouterr().err
    # The guard is the whole point: every write path deletes what the source
    # lacks, so without it an empty source wipes both mirrors.
    for mirror in mirrors:
        assert (mirror / 'SKILL.md').exists()
        assert (mirror / 'scripts' / 'world.py').exists()
