'''Tests for the shared parsing/table engine in dev-phase-lib/tracklib.py.'''

import json

import pytest

import tracklib as tl

PACKAGE_JSON = '''{
  "name": "demo",
  "version": "1.2.3",
  "scripts": {}
}
'''

# (label, version_attr, file text) — one per version-file dialect the helpers must serve.
# 'json-quoted-attr' is the legacy spelling with the quotes baked into version_attr; it stays
# supported so the optional-key-quote change is a strict superset.
VERSION_FORMS = [
    ('py-single', '__version__', "__version__ = '1.2.3'\n"),
    ('py-double', '__version__', '__version__ = "1.2.3"\n'),
    ('json', 'version', PACKAGE_JSON),
    ('json-quoted-attr', '"version"', PACKAGE_JSON),
    ('yaml', 'version', 'name: demo\nversion: "1.2.3"\n'),
]

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


def _version_repo(tmp_path, name, text):
    '''Write *text* to tmp_path/name and return the (root, cfg) pair read_version wants.'''
    (tmp_path / name).write_text(text, encoding='utf-8')
    return tmp_path, {'version_file': name}


class TestReadVersion:
    @pytest.mark.parametrize('label,attr,text', VERSION_FORMS, ids=[f[0] for f in VERSION_FORMS])
    def test_reads_every_dialect(self, tmp_path, label, attr, text):
        root, cfg = _version_repo(tmp_path, 'vfile', text)
        cfg['version_attr'] = attr
        assert tl.read_version(root, cfg) == '1.2.3'

    def test_missing_file_is_none(self, tmp_path):
        assert tl.read_version(tmp_path, {'version_file': 'nope.py'}) is None

    def test_no_literal_is_none(self, tmp_path):
        root, cfg = _version_repo(tmp_path, 'vfile', 'nothing to see here\n')
        assert tl.read_version(root, cfg) is None

    def test_attr_defaults_to_dunder_version(self, tmp_path):
        root, cfg = _version_repo(tmp_path, 'vfile', "__version__ = '1.2.3'\n")
        assert tl.read_version(root, cfg) == '1.2.3'   # cfg carries no version_attr


class TestBumpVersionText:
    def test_preserves_double_quotes(self):
        assert tl.bump_version_text('__version__ = "1.2.3"\n', '__version__', '1.3.0') \
            == '__version__ = "1.3.0"\n'

    def test_preserves_single_quotes(self):
        assert tl.bump_version_text("__version__ = '1.2.3'\n", '__version__', '1.3.0') \
            == "__version__ = '1.3.0'\n"

    def test_json_stays_valid_json(self):
        out = tl.bump_version_text(PACKAGE_JSON, 'version', '1.3.0')
        assert json.loads(out)['version'] == '1.3.0'
        assert json.loads(out)['name'] == 'demo'

    def test_only_first_occurrence_is_rewritten(self):
        text = '__version__ = "1.2.3"\nother = "x"\n__version__ = "1.2.3"\n'
        out = tl.bump_version_text(text, '__version__', '1.3.0')
        assert out.count('1.3.0') == 1
        assert out.count('1.2.3') == 1

    def test_no_match_raises_naming_the_file(self):
        with pytest.raises(SystemExit) as exc:
            tl.bump_version_text('nothing here\n', '__version__', '1.3.0', where='src/__init__.py')
        assert 'src/__init__.py' in str(exc.value)

    @pytest.mark.parametrize('label,attr,text', VERSION_FORMS, ids=[f[0] for f in VERSION_FORMS])
    def test_round_trip_parity_with_read_version(self, tmp_path, label, attr, text):
        '''bump then read must agree — the guard against the two patterns drifting apart.'''
        bumped = tl.bump_version_text(text, attr, '9.9.9')
        root, cfg = _version_repo(tmp_path, 'vfile', bumped)
        cfg['version_attr'] = attr
        assert tl.read_version(root, cfg) == '9.9.9'


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
        with pytest.raises(ValueError):
            tl.append_table_rows('no table here', ('Phase', 'Items', 'Status'), ['| x |'])


class TestCellId:
    def test_unlinks_a_markdown_id_cell(self):
        assert tl.cell_id('[I-10](improvements/I-10.md)') == 'I-10'

    def test_passes_a_bare_id_through(self):
        assert tl.cell_id('P-15') == 'P-15'

    def test_tolerates_surrounding_whitespace(self):
        assert tl.cell_id('  [F-4](fixes/F-4.md)  ') == 'F-4'

    def test_non_link_cell_is_returned_unchanged(self):
        # Trailing prose means the cell is not exactly a link, so there is no id to extract.
        # Return it verbatim rather than guess, and let the equality check simply not match.
        assert tl.cell_id('[I-3](improvements/I-3.md) (superseded)') == \
            '[I-3](improvements/I-3.md) (superseded)'


class TestIdMatcher:
    '''Regression: cut_release.py stamped every row whose ID cell *contained* the id.

    `id_matcher` is the predicate the three cut_release.py call sites pass to
    `update_table_rows`, so testing it here covers the production path — reverting a call
    site to an inline `in` test now means dropping a tested helper, not editing past a test.

    The table mirrors the real codeblox IMPROVEMENTS.md, where the older I-1 row carries a
    bare id and the newer I-10 row a markdown link, so a correct predicate handles both.
    '''

    TABLE = (
        '| ID | Idea | Notes |\n'
        '|---|---|---|\n'
        '| I-1 | first | 🚧 In progress. |\n'
        '| [I-10](improvements/I-10.md) | tenth | 🚧 In progress. |\n'
    )

    def test_substring_predicate_selects_the_sibling(self):
        # Pins the old behaviour, so the regression below cannot silently stop testing it.
        hits = [c[0] for c in self._select(lambda c: bool(c) and 'I-1' in c[0])]
        assert hits == ['I-1', '[I-10](improvements/I-10.md)']

    def test_selects_only_the_named_row(self):
        hits = [c[0] for c in self._select(tl.id_matcher('I-1'))]
        assert hits == ['I-1']

    def test_matches_a_linked_cell_by_its_bare_id(self):
        hits = [c[0] for c in self._select(tl.id_matcher('I-10'))]
        assert hits == ['[I-10](improvements/I-10.md)']

    def test_ignores_an_id_no_row_carries(self):
        assert self._select(tl.id_matcher('I-2')) == []

    def test_the_sibling_row_is_left_unstamped(self):
        out = self._stamp('I-1')
        assert '| I-1 | first | ✅ Done in v0.7.0. |' in out
        assert '| [I-10](improvements/I-10.md) | tenth | 🚧 In progress. |' in out

    def test_the_linked_row_is_still_reachable_by_its_own_id(self):
        out = self._stamp('I-10')
        assert '| [I-10](improvements/I-10.md) | tenth | ✅ Done in v0.7.0. |' in out
        assert '| I-1 | first | 🚧 In progress. |' in out

    def _stamp(self, iid):
        '''Apply the release done-marker the way cut_release.py does.'''
        return tl.update_table_rows(
            self.TABLE, ('ID', 'Idea', 'Notes'),
            key_pred=tl.id_matcher(iid),
            transform=lambda c: c[:-1] + ['✅ Done in v0.7.0.'],
        )

    def _select(self, pred):
        '''Rows a predicate selects, without transforming anything.'''
        seen = []

        def probe(cells):
            if pred(cells):
                seen.append(cells)
            return False    # never match, so transform is never applied

        tl.update_table_rows(self.TABLE, ('ID', 'Idea', 'Notes'),
                             key_pred=probe, transform=lambda c: c)
        return seen
