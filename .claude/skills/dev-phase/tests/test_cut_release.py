'''Tests for cut_release's version bump.

Regression origin: the bump only matched ``attr = 'x'`` (assignment form), so on a JSON
version file it silently substituted nothing while still reporting 'bump ... -> X.Y.Z'.
The release then failed the coherence gate with a version that had never moved.
'''

import json

import pytest

from cut_release import bump_version_text


def test_bumps_a_python_assignment():
    got = bump_version_text("__version__ = '0.2.0'\n", '__version__', '0.3.0')
    assert got == "__version__ = '0.3.0'\n"


def test_bumps_a_json_mapping_key():
    got = bump_version_text('  "version": "0.2.0",\n', '"version"', '0.3.0')
    assert got == '  "version": "0.3.0",\n'


def test_json_stays_valid_after_a_bump():
    src = json.dumps({'name': 'codeblox', 'version': '0.2.0'}, indent=2)
    got = bump_version_text(src, '"version"', '0.3.0')
    assert json.loads(got)['version'] == '0.3.0'


def test_only_the_first_literal_is_touched():
    src = '"version": "0.2.0"\n"version": "9.9.9"\n'
    got = bump_version_text(src, '"version"', '0.3.0')
    assert got == '"version": "0.3.0"\n"version": "9.9.9"\n'


def test_a_missing_literal_fails_loudly_instead_of_no_oping():
    with pytest.raises(SystemExit) as excinfo:
        bump_version_text('name = "codeblox"\n', '__version__', '0.3.0')
    assert 'version bump failed' in str(excinfo.value)
