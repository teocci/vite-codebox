'''The preflight report — specifically, that it says what a block is worth.

Only the world rung is covered here. The binary and auth rungs are exercised
through test_resolve_codeblox.py and the Go integration tests; what was missing
was that preflight is the first thing an agent runs and the only place it could
have learned the scale before building at the wrong one.
'''

from __future__ import annotations

import doctor
import world

CONTRACT = {
    'config': {
        'blockSize': 0.02, 'blockLabel': '2 cm', 'extent': 32,
        'gridStep': 1, 'boundBlocks': 1600, 'heightBlocks': 3200,
    },
    'palette': {'oak': {'family': 'opaque'}},
    'ops': [{'op': 'box', 'fields': {}}],
}


def test_the_world_check_states_what_a_block_is_worth(monkeypatch):
    # Preflight already fetched the contract; dropping the one derived number a
    # builder needs from it meant the next step had to guess.
    monkeypatch.setattr(world, 'fetch', lambda _binary: CONTRACT)
    detail = doctor.check_world('codeblox')['detail']
    assert '2 cm' in detail
    assert '50 blocks per metre' in detail


def test_the_world_check_still_reports_the_buildable_box(monkeypatch):
    monkeypatch.setattr(world, 'fetch', lambda _binary: CONTRACT)
    check = doctor.check_world('codeblox')
    assert check['ok'] is True
    assert '±1600' in check['detail']
    assert check['bounds']['y'] == [0, 3200]


def test_an_unreachable_server_is_a_network_failure(monkeypatch):
    def refuse(_binary):
        raise world.WorldError('connection refused')

    monkeypatch.setattr(world, 'fetch', refuse)
    check = doctor.check_world('codeblox')
    assert check['ok'] is False
    assert check['exit'] == doctor.EXIT_NETWORK
