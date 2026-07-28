'''Tests for the PLAN.md ledger handling in dev-phase-start/scaffold.py.

Named test_scaffold_plan.py, not test_scaffold.py: phase-tracker/tests/ already owns that
basename, neither tests dir has an __init__.py, and the repo has no pytest config — so two
same-named modules would collide under the default prepend import mode.
'''

import json

import order
import pytest
import scaffold

PLAN_TABLE = ('| Phase | Items | Depends | Release | Version | Status |\n'
              '|-------|-------|---------|---------|---------|--------|\n')
PROGRESS_TABLE = '# Progress\n\n| Phase | Title | Status |\n|---|---|---|\n'
IMPROVEMENTS_TABLE = '# Improvements\n\n| ID | Idea | Notes |\n|---|---|---|\n'
FIXES_TABLE = '# Fixes\n\n| ID | Symptom | Fix | Version | Notes |\n|---|---|---|---|---|\n'


def row(phase, items='I-1', depends='—', release='R1', version='(pending)', status='pending'):
    return f'| {phase} | {items} | {depends} | {release} | {version} | {status} |\n'


def plan_doc(*rows, approved='2026-01-01', branch='feat/first', cadence='per-phase'):
    head = (f'# Active Plan\n\n**Approved:** {approved}  **Branch:** {branch}  '
            f'**Cadence:** {cadence}\n\n')
    return head + PLAN_TABLE + ''.join(rows)


def ph(title, **kw):
    '''One spec phase carrying a single improvement item.'''
    items = [{'kind': 'improvement', 'title': f'{title} item', 'summary': 'a summary'}]
    return {'title': title, 'items': items, **kw}


def spec_of(*phases, **top):
    base = {'approved': '2026-07-28', 'branch': 'feat/first', 'cadence': 'per-phase'}
    return {**base, 'phases': list(phases), **top}


@pytest.fixture
def project(tmp_path, monkeypatch):
    '''A throwaway repo root with the three sibling ledgers and no PLAN.md.'''
    (tmp_path / '.git').mkdir()
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'PROGRESS.md').write_text(PROGRESS_TABLE, encoding='utf-8')
    (docs / 'IMPROVEMENTS.md').write_text(IMPROVEMENTS_TABLE, encoding='utf-8')
    (docs / 'FIXES.md').write_text(FIXES_TABLE, encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scaffold.tl, 'git_branch', lambda root: 'feat/first')
    return tmp_path


class PlanFile:
    '''Read/write the throwaway project's PLAN.md, and seed PROGRESS.md for id allocation.'''

    def __init__(self, path, progress):
        self.path = path
        self._progress = progress

    def write(self, text):
        self.path.write_text(text, encoding='utf-8')

    def read(self):
        return self.path.read_text(encoding='utf-8')

    def seed_progress(self, last_phase):
        rows = ''.join(f'| {n} | phase {n} | planned |\n' for n in range(last_phase + 1))
        self._progress.write_text(PROGRESS_TABLE + rows, encoding='utf-8')


@pytest.fixture
def plan(project):
    return PlanFile(project / 'docs' / 'PLAN.md', project / 'docs' / 'PROGRESS.md')


def statuses(text):
    return {r['phase']: r['status'] for r in scaffold.tl.parse_plan(text)['rows']}


def depends_of(text, pid):
    return next(r['depends'] for r in scaffold.tl.parse_plan(text)['rows'] if r['phase'] == pid)


# ── the three orderings a second plan can have (asserted through order.py) ───

class TestScenarios:
    '''P-0..P-4 exist and are untouched; a second plan is scaffolded alongside them.'''

    @pytest.fixture(autouse=True)
    def five_phases(self, plan):
        plan.seed_progress(4)
        plan.write(plan_doc(
            row('P-0'), row('P-1', depends='P-0'), row('P-2', depends='P-1'),
            row('P-3', depends='P-2'), row('P-4', depends='P-3')))

    def test_scenario_1_defers_the_old_plan(self, plan):
        '''The old plan needs the new one first: defer it, and next starts the new group.'''
        result = scaffold.scaffold(
            spec_of(ph('R one', release='R9'), ph('R two', release='R9', depends=[0]),
                    defers=['P-0']), False)

        assert result['plan_mode'] == 'append'
        assert result['deferred'] == ['P-0']
        assert depends_of(plan.read(), 'P-0') == 'P-6'   # this run's terminal phase
        assert order.build()['ready'] == ['P-5']

    def test_scenario_2_new_plan_waits_on_an_existing_phase(self, plan):
        result = scaffold.scaffold(
            spec_of(ph('R one', release='R9', depends=['P-3'])), False)

        assert result['plan_mode'] == 'append'
        assert depends_of(plan.read(), 'P-5') == 'P-3'
        assert order.build()['ready'] == ['P-0']

    def test_scenario_3_independent_plans_are_parallelizable(self, plan):
        scaffold.scaffold(spec_of(ph('R one', release='R9')), False)

        data = order.build()
        assert data['ready'] == ['P-0', 'P-5']
        assert data['parallelizable'] == ['P-0', 'P-5']

    def test_existing_rows_keep_status_and_version(self, plan):
        plan.write(plan_doc(
            row('P-0', release='R1', version='0.3.0', status='released'),
            row('P-1', depends='P-0', release='R2', status='in-progress'),
            row('P-2', depends='P-1', release='R3')))

        scaffold.scaffold(spec_of(ph('R one', release='R9')), False)

        text = plan.read()
        assert statuses(text) == {'P-0': 'released', 'P-1': 'in-progress',
                                 'P-2': 'pending', 'P-5': 'pending'}
        assert '| P-0 | I-1 | — | R1 | 0.3.0 | released |' in text

    def test_append_keeps_the_ledger_header(self, plan):
        scaffold.scaffold(spec_of(ph('R one', release='R9'), branch='feat/second'), False)

        meta = scaffold.tl.parse_plan(plan.read())['meta']
        assert meta['approved'] == '2026-01-01'
        assert meta['branch'] == 'feat/first'

    def test_branch_divergence_is_warned_not_merged(self, plan):
        result = scaffold.scaffold(
            spec_of(ph('R one', release='R9'), branch='feat/second'), False)

        assert any('feat/second' in w for w in result['warnings'])


# ── classify_plan: fresh only when there is provably nothing to lose ─────────

class TestClassifyFresh:
    @pytest.mark.parametrize('text', [
        '',
        '   \n\n',
        'No active plan.\n',
        '# Active Plan\n\n> No active plan.\n',
        plan_doc(),  # header + divider, zero rows
    ])
    def test_states_with_no_rows_are_fresh(self, text):
        assert scaffold.classify_plan(text) == 'fresh'

    def test_a_populated_ledger_is_append(self):
        assert scaffold.classify_plan(plan_doc(row('P-0'))) == 'append'

    def test_the_stub_phrase_in_a_note_does_not_beat_a_real_table(self):
        text = plan_doc(row('P-0')) + '\nReset to "No active plan." when every row is released.\n'
        assert scaffold.classify_plan(text) == 'append'


class TestClassifyRefusals:
    def _refusal(self, text):
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.classify_plan(text)
        return exc.value.payload

    def test_merge_conflict_marker_refuses(self):
        text = plan_doc() + '<<<<<<< HEAD\n' + row('P-0') + row('P-1')
        assert self._refusal(text)['code'] == 'malformed'

    def test_a_row_with_a_dropped_cell_refuses(self):
        text = plan_doc(row('P-0'), '| P-1 | I-2 | — | R2 | pending |\n', row('P-2'))
        payload = self._refusal(text)
        assert payload['code'] == 'malformed'
        assert (payload['physical_rows'], payload['parsed_rows']) == (3, 2)

    def test_partial_malformation_never_reads_as_all_released(self):
        '''Skipping the malformed pending row would leave "all released" -> a wholesale rewrite.'''
        text = plan_doc(
            row('P-0', status='released'), row('P-1', status='released'),
            '| P-2 | I-3 | — | R3 | pending |\n')
        assert self._refusal(text)['code'] == 'malformed'

    def test_content_without_a_ledger_table_refuses(self):
        assert self._refusal('# Active Plan\n\nsome prose, no table\n')['code'] == 'unparseable'

    def test_a_fully_released_ledger_refuses_with_the_drain_message(self):
        payload = self._refusal(plan_doc(
            row('P-0', status='released'), row('P-1', status='released')))
        assert payload['code'] == 'not-drained'
        assert payload['released'] == ['P-0', 'P-1']
        assert 'drain' in payload['error']


class TestNothingIsWrittenOnRefusal:
    def test_refusal_leaves_the_ledger_byte_identical(self, plan):
        before = plan_doc() + '<<<<<<< HEAD\n' + row('P-0') + row('P-1')
        plan.write(before)

        with pytest.raises(scaffold.Refusal):
            scaffold.scaffold(spec_of(ph('R one', release='R9')), False)

        assert plan.read() == before

    def test_dry_run_writes_nothing_and_reports_the_mode(self, plan):
        before = plan_doc(row('P-0'))
        plan.write(before)

        result = scaffold.scaffold(spec_of(ph('R one', release='R9')), True)

        assert result['plan_mode'] == 'append'
        assert result['dry_run'] is True
        assert plan.read() == before
        assert not (plan.path.parent / 'phases').exists()

    def test_main_exits_2_on_a_refusal(self, plan, tmp_path, monkeypatch, capsys):
        plan.write(plan_doc(row('P-0', status='released')))
        spec_file = tmp_path / 'spec.json'
        spec_file.write_text(json.dumps(spec_of(ph('R one', release='R9'))), encoding='utf-8')
        monkeypatch.setattr('sys.argv', ['scaffold.py', '--spec', str(spec_file)])

        assert scaffold.main() == 2
        assert json.loads(capsys.readouterr().err)['code'] == 'not-drained'


# ── forward edges: depends by index and by existing id ───────────────────────

class TestDepends:
    @pytest.fixture(autouse=True)
    def one_phase(self, plan):
        plan.seed_progress(0)
        plan.write(plan_doc(row('P-0')))

    def test_int_index_points_at_an_earlier_phase_in_this_spec(self, plan):
        scaffold.scaffold(spec_of(ph('a', release='R9'), ph('b', release='R9', depends=[0])), False)
        assert depends_of(plan.read(), 'P-2') == 'P-1'

    def test_mixed_ints_and_ids_are_deduped_in_order(self, plan):
        scaffold.scaffold(
            spec_of(ph('a', release='R9'),
                    ph('b', release='R9', depends=[0, 'P-0', 'P-0'])), False)
        assert depends_of(plan.read(), 'P-2') == 'P-1, P-0'

    def test_no_depends_renders_the_empty_marker(self, plan):
        scaffold.scaffold(spec_of(ph('a', release='R9')), False)
        assert depends_of(plan.read(), 'P-1') == '—'

    @pytest.mark.parametrize('depends, code', [
        (['P-99'], 'unknown-depends'),
        ([-1], 'bad-depends'),
        ([0], 'bad-depends'),      # forward/self reference from the first spec phase
        ([None], 'bad-depends'),
    ])
    def test_bad_depends_refuses_and_writes_nothing(self, plan, depends, code):
        before = plan.read()
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a', release='R9', depends=depends)), False)
        assert exc.value.payload['code'] == code
        assert plan.read() == before


# ── reverse edges: defers ────────────────────────────────────────────────────

class TestDefers:
    @pytest.fixture(autouse=True)
    def two_phases(self, plan):
        plan.seed_progress(1)
        plan.write(plan_doc(row('P-0', depends='P-9'), row('P-1')))

    def test_existing_depends_are_preserved_not_replaced(self, plan):
        scaffold.scaffold(spec_of(ph('a', release='R9'), defers=['P-0']), False)
        assert depends_of(plan.read(), 'P-0') == 'P-9, P-2'

    def test_only_the_depends_cell_of_the_named_row_changes(self, plan):
        scaffold.scaffold(spec_of(ph('a', release='R9'), defers=['P-0']), False)
        text = plan.read()
        assert '| P-1 | I-1 | — | R1 | (pending) | pending |' in text
        assert '| P-0 | I-1 | P-9, P-2 | R1 | (pending) | pending |' in text

    def test_all_terminals_are_added_when_the_run_has_several(self, plan):
        scaffold.scaffold(
            spec_of(ph('a', release='R9'), ph('b', release='R9'), defers=['P-1']), False)
        assert depends_of(plan.read(), 'P-1') == 'P-2, P-3'

    @pytest.mark.parametrize('status, code', [
        ('in-progress', 'defer-not-pending'),
        ('done', 'defer-not-pending'),
        ('released', 'defer-not-pending'),
    ])
    def test_only_a_pending_row_can_be_deferred(self, plan, status, code):
        plan.write(plan_doc(row('P-0', status=status), row('P-1')))
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a', release='R9'), defers=['P-0']), False)
        assert exc.value.payload['code'] == code

    def test_unknown_id_refuses(self, plan):
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a', release='R9'), defers=['P-99']), False)
        assert exc.value.payload['code'] == 'unknown-defers'

    def test_a_cycle_refuses_and_writes_nothing(self, plan):
        '''Deferring P-0 behind a phase that itself waits on P-0.'''
        before = plan.read()
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(
                spec_of(ph('a', release='R9', depends=['P-0']), defers=['P-0']), False)
        assert exc.value.payload['code'] == 'cycle'
        assert sorted(exc.value.payload['cycle']) == ['P-0', 'P-2']
        assert plan.read() == before

    def test_defers_without_an_active_plan_refuses(self, project, plan):
        plan.path.unlink(missing_ok=True)
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a'), defers=['P-0']), False)
        assert exc.value.payload['code'] == 'defers-without-plan'


# ── release tags ─────────────────────────────────────────────────────────────

class TestRelease:
    @pytest.fixture(autouse=True)
    def one_shipped_phase(self, plan):
        plan.seed_progress(1)
        plan.write(plan_doc(row('P-0', release='R1', version='0.3.0', status='released'),
                            row('P-1', release='R2')))

    def test_release_is_required_when_appending(self, plan):
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a')), False)
        payload = exc.value.payload
        assert payload['code'] == 'release-required'
        assert payload['existing_releases'] == ['R1', 'R2']

    def test_reusing_a_shipped_tag_refuses(self, plan):
        with pytest.raises(scaffold.Refusal) as exc:
            scaffold.scaffold(spec_of(ph('a', release='R1')), False)
        assert exc.value.payload['code'] == 'release-shipped'

    def test_joining_an_unreleased_group_is_allowed(self, plan):
        scaffold.scaffold(spec_of(ph('a', release='R2')), False)
        assert '| P-2 | I-2 | — | R2 | (pending) | pending |' in plan.read()

    def test_item_ids_never_collide_with_the_ledgers_items_column(self, plan):
        '''The Items column is the second id source, for the same double-stamp reason.'''
        result = scaffold.scaffold(spec_of(ph('a', release='R9')), False)
        assert result['phases'] == ['P-2']
        assert 'I-2' in result['improvements'][0]

    def test_a_fresh_plan_still_defaults_the_tag(self, plan):
        plan.path.unlink()
        scaffold.scaffold(spec_of(ph('a'), ph('b')), False)
        text = plan.read()
        assert '| R1 |' in text and '| R2 |' in text


# ── fresh writes and id allocation ───────────────────────────────────────────

class TestFreshAndIds:
    def test_a_fresh_write_uses_the_spec_meta(self, plan):
        scaffold.scaffold(spec_of(ph('a'), approved='2026-07-28', branch='feat/new'), False)
        meta = scaffold.tl.parse_plan(plan.read())['meta']
        assert meta['approved'] == '2026-07-28'
        assert meta['branch'] == 'feat/new'

    def test_ids_are_allocated_next_free_across_an_append(self, project, plan):
        plan.seed_progress(18)
        (project / 'docs' / 'IMPROVEMENTS.md').write_text(
            IMPROVEMENTS_TABLE + '| [I-10](improvements/I-10.md) | idea | done |\n',
            encoding='utf-8')
        plan.write(plan_doc(row('P-18')))

        result = scaffold.scaffold(spec_of(ph('a', release='R9')), False)

        assert result['phases'] == ['P-19']
        assert 'I-11' in result['improvements'][0]
        assert (project / 'docs' / 'phases' / 'phase-19.md').exists()

    def test_ids_never_collide_when_progress_lags_the_ledger(self, project, plan):
        '''A duplicate phase id would make finalize/release stamp two rows.'''
        plan.seed_progress(0)
        plan.write(plan_doc(row('P-0'), row('P-1'), row('P-2')))

        result = scaffold.scaffold(spec_of(ph('a', release='R9')), False)

        assert result['phases'] == ['P-3']
        ids = [r['phase'] for r in scaffold.tl.parse_plan(plan.read())['rows']]
        assert len(ids) == len(set(ids))

    def test_new_rows_land_before_trailing_content(self, plan):
        plan.seed_progress(0)
        plan.write(plan_doc(row('P-0')) + '\nA note under the ledger.\n')

        scaffold.scaffold(spec_of(ph('a', release='R9')), False)

        text = plan.read()
        assert text.index('| P-1 |') < text.index('A note under the ledger.')

    def test_the_sibling_ledgers_still_append(self, project, plan):
        plan.seed_progress(0)
        plan.write(plan_doc(row('P-0')))
        existing = (project / 'docs' / 'IMPROVEMENTS.md').read_text(encoding='utf-8')

        scaffold.scaffold(spec_of(ph('a', release='R9')), False)

        after = (project / 'docs' / 'IMPROVEMENTS.md').read_text(encoding='utf-8')
        assert after.startswith(existing.rstrip('\n'))
        assert 'I-2' in after
