'''Tests for the coherence checker's pure helpers + the new --json emitter.'''

import json

import check_coherence as cc


class TestReleaseTopVersion:
    def test_table_row(self):
        assert cc._release_top_version('| v1.2.0 | Theme | 2025-01-01 |') == '1.2.0'

    def test_legacy_prose_heading(self):
        assert cc._release_top_version('## 1.3.0 - 2025-01-01') == '1.3.0'

    def test_none_when_absent(self):
        assert cc._release_top_version('no release rows here') is None


class TestEmitJson:
    def test_shape_and_failed_count(self, capsys):
        cc._emit_json([(True, 'a'), (False, 'b')], 1)
        payload = json.loads(capsys.readouterr().out)
        assert payload['ok'] is False
        assert payload['failed'] == 1
        assert payload['checks'] == [{'ok': True, 'msg': 'a'}, {'ok': False, 'msg': 'b'}]

    def test_all_pass(self, capsys):
        cc._emit_json([(True, 'a')], 0)
        payload = json.loads(capsys.readouterr().out)
        assert payload['ok'] is True
        assert payload['failed'] == 0
