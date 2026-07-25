'''Tests for the dependency-wave sequencing in dev-phase-workflow/order.py.'''

import order


def _row(phase: str, status: str, depends: list[str] | None = None) -> dict:
    return {'phase': phase, 'status': status, 'depends_list': depends or []}


class TestComputeWaves:
    def test_linear_chain_is_one_phase_per_wave(self):
        rows = [
            _row('P-1', 'planned'),
            _row('P-2', 'planned', ['P-1']),
            _row('P-3', 'planned', ['P-2']),
        ]
        waves, diag = order.compute_waves(rows)
        assert waves == [['P-1'], ['P-2'], ['P-3']]
        assert diag == {'blocked': {}, 'unknown': {}}

    def test_independent_phases_share_one_wave(self):
        rows = [_row('P-1', 'planned'), _row('P-2', 'planned'), _row('P-3', 'planned', ['P-1'])]
        waves, _ = order.compute_waves(rows)
        assert waves[0] == ['P-1', 'P-2']  # sorted, parallelizable
        assert waves[1] == ['P-3']

    def test_done_phase_satisfies_dependents(self):
        rows = [_row('P-1', 'done'), _row('P-2', 'planned', ['P-1'])]
        waves, _ = order.compute_waves(rows)
        assert waves == [['P-2']]  # P-1 is done, not scheduled again

    def test_released_phase_is_treated_as_satisfied(self):
        rows = [_row('P-1', 'released'), _row('P-2', 'planned', ['P-1'])]
        waves, _ = order.compute_waves(rows)
        assert waves == [['P-2']]

    def test_cycle_is_reported_as_blocked_not_scheduled(self):
        rows = [_row('P-1', 'planned', ['P-2']), _row('P-2', 'planned', ['P-1'])]
        waves, diag = order.compute_waves(rows)
        assert waves == []
        assert set(diag['blocked']) == {'P-1', 'P-2'}

    def test_unknown_dependency_is_flagged(self):
        rows = [_row('P-2', 'planned', ['P-9'])]
        _, diag = order.compute_waves(rows)
        assert diag['unknown'] == {'P-2': ['P-9']}


class TestRender:
    def test_next_lists_ready_and_flags_parallelism(self):
        data = {'plan_active': True, 'waves': [], 'ready': ['P-1', 'P-2'],
                'parallelizable': ['P-1', 'P-2'], 'blocked': {}, 'unknown_deps': {}}
        out = order.render(data, 'next')
        assert 'ready now: P-1, P-2' in out
        assert 'separate session' in out

    def test_suggest_marks_parallel_waves(self):
        data = {'plan_active': True, 'waves': [['P-1', 'P-2'], ['P-3']], 'ready': [],
                'parallelizable': [], 'blocked': {}, 'unknown_deps': {}}
        out = order.render(data, 'suggest')
        assert 'wave 1: P-1, P-2  (parallel)' in out
        assert 'wave 2: P-3' in out

    def test_inactive_plan(self):
        assert order.render({'plan_active': False}, 'next') == 'plan: none active'
