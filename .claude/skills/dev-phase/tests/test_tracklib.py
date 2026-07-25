'''Tests for the shared parsing/table engine in dev-phase-lib/tracklib.py.'''

import tracklib as tl

PLAN = '''# Active plan

**Approved:** 2025-01-01  **Branch:** feat/x  **Cadence:** per-phase

| Phase | Items | Depends | Release | Version | Status |
|---|---|---|---|---|---|
| P-1 | I-1 | — | R1 | (pending) | done |
| P-2 | I-2 | P-1 | R1 | (pending) | planned |
| P-3 | I-3 | P-2 | R2 | (pending) | planned |
'''

CHANGELOG = '''# Changelog

## [Unreleased]
- Added foo
- Fixed bar

## [1.2.0] - 2025-01-01
- old entry
'''


class TestSemver:
    def test_valid(self):
        assert tl.is_semver('1.2.3')
        assert tl.is_semver('0.1.0')

    def test_invalid(self):
        assert not tl.is_semver('nope')
        assert not tl.is_semver('')
        assert not tl.is_semver(None)


class TestPlanParsing:
    def test_meta_is_parsed(self):
        meta = tl.parse_plan(PLAN)['meta']
        assert meta['approved'] == '2025-01-01'
        assert meta['branch'] == 'feat/x'
        assert meta['cadence'] == 'per-phase'

    def test_rows_and_depends_list(self):
        rows = tl.parse_plan(PLAN)['rows']
        assert [r['phase'] for r in rows] == ['P-1', 'P-2', 'P-3']
        assert rows[0]['depends_list'] == []          # em-dash → empty
        assert rows[1]['depends_list'] == ['P-1']

    def test_ready_excludes_done_and_blocked(self):
        rows = tl.parse_plan(PLAN)['rows']
        assert [r['phase'] for r in tl.plan_ready(rows)] == ['P-2']

    def test_stub_detection(self):
        assert tl.plan_is_stub('No active plan.')
        assert not tl.plan_is_stub(PLAN)


class TestChangelog:
    def test_top_version_skips_unreleased(self):
        assert tl.changelog_top_version(CHANGELOG) == '1.2.0'

    def test_unreleased_bullets(self):
        assert tl.changelog_unreleased(CHANGELOG) == ['- Added foo', '- Fixed bar']


class TestTableEngine:
    TABLE = '| Phase | Items | Status |\n|---|---|---|\n| P-1 | I-1 | done |\n'

    def test_append_after_last_row(self):
        out = tl.append_table_rows(self.TABLE, ('Phase', 'Items', 'Status'), ['| P-2 | I-2 | planned |'])
        lines = out.splitlines()
        assert lines[-1] == '| P-2 | I-2 | planned |'
        assert lines[2] == '| P-1 | I-1 | done |'   # existing row preserved

    def test_prepend_after_divider(self):
        out = tl.prepend_table_rows(self.TABLE, ('Phase', 'Items', 'Status'), ['| P-0 | I-0 | done |'])
        assert out.splitlines()[2] == '| P-0 | I-0 | done |'

    def test_update_matching_row(self):
        out = tl.update_table_rows(
            self.TABLE, ('Phase', 'Items', 'Status'),
            key_pred=lambda c: c[0] == 'P-1',
            transform=lambda c: [c[0], c[1], 'released'],
        )
        assert '| P-1 | I-1 | released |' in out

    def test_missing_table_raises(self):
        import pytest
        with pytest.raises(ValueError):
            tl.append_table_rows('no table here', ('Phase', 'Items', 'Status'), ['| x |'])
