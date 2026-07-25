# Tracking conventions — project overrides (codeblox)

Project bindings for the `dev-phase-*` skill family. The reusable base lives in
`.claude/dev-phase/dev-phase-workflow/references/conventions.md`; this file **overrides and
extends** it. Resolution order is always: base conventions → these overrides.

```toml
package = "codeblox"
version_file = "package.json"
version_attr = "\"version\""
version_dynamic = false
test_cmd = "npm test"

release_branch = "main"
integration = "trunk"
concurrency = "single"

[paths]
progress = "docs/PROGRESS.md"
plan = "docs/PLAN.md"
release_index = "docs/RELEASE.md"
changelog = "CHANGELOG.md"
improvements = "docs/IMPROVEMENTS.md"
fixes = "docs/FIXES.md"
phases_dir = "docs/phases"
improvements_dir = "docs/improvements"
fixes_dir = "docs/fixes"
```

## Overrides and project-specific notes

### This is a JavaScript project, not Python
The base defaults assume a Python package (`src/__init__.py`, `pytest`). Here the version
single-source-of-truth is `package.json`'s `"version"` key and the suite is `npm test`
(vitest). `version_dynamic = false` — there is no `pyproject.toml`, so the base's
"no literal `version=`" assertion is skipped.

`version_attr` is the quoted JSON key `"version"` (escaped in TOML). `tracklib.read_version`
accepts either `key = "x"` or `key: "x"` so the same helper reads a JS `package.json` and a
Python `__init__.py`.

### Node is installed via fnm and is not on PATH
Non-interactive shells need the fnm install dir prepended before `npm`/`node`/`npx` resolve:

```powershell
$env:PATH = "C:\Users\teocci\AppData\Roaming\fnm\node-versions\v24.13.1\installation;$env:PATH"
```

### Two Python venvs are irrelevant here
The product is JS. The repo `.venv/` exists solely to run the `dev-phase-*` skill scripts
(stdlib-only — no `requirements.txt`, nothing to install). It is gitignored.

### Skill location deviates from the documented path
The family lives at `.claude/dev-phase/<skill>/scripts/`, not `.claude/skills/<skill>/scripts/`
as the SKILL.md bodies show. The `tracklib` import bootstrap (`parents[2]`) and
`tests/conftest.py` (`parents[1]`) both resolve correctly at this nesting, so run the scripts by
their real path:

```bash
.venv/Scripts/python .claude/dev-phase/dev-phase-status/scripts/status.py
```

### `integration = trunk`
Single operator, agent-driven. Commits and release tags land directly on `main`; the base's
branch guards (§7b guard 1) are inert in trunk mode. Escalate to a short-lived branch only for
risky work, merging before the release.

### Version bump baseline
`v0.2.0` is the baseline release covering the pre-tracking work (Phases 1–2, built before this
tracking structure existed). Phase and item ids therefore start allocating at `P-3` / `I-1` / `F-1`.
