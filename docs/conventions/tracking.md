# Tracking conventions — project overrides (codeblox)

Project bindings for the `dev-phase-*` skill family. The reusable base lives in
`.claude/skills/dev-phase-workflow/references/conventions.md`; this file **overrides and
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

### Python runs from `.venv/`
The product is JS, but several things here are Python, and they all use the repo `.venv/` — never
the system interpreter. Today that is `codeblox-builder`'s own suite (258 pytest, counted in the
product totals), the `dev-phase-*` skill scripts, and `scripts/py/`. All stdlib-only, so there is no
`requirements.txt` and nothing to install. It is gitignored.

This is not an exception to justify; it is simply where Python runs in this repo.

### Mirroring the skill is a manual chore step
`codeblox-builder` is authored once in `.claude/` and copied to `.codex/` and `.agents/`. That copy
is **not** part of the product surface: it is not an npm script and it does not run under
`npm test`. What deploys from this repo is the browser build and the ws server, and a stale mirror
must never be able to fail the suite that gates them.

So drift detection is deliberate rather than automatic — there is no clean event to trigger it on:

```bash
$VENV/python scripts/py/mirror_skill.py --check   # exits 1 on drift, writes nothing
$VENV/python scripts/py/mirror_skill.py           # propagate
```

Run `--check` before committing a change to the skill, propagate, and commit the mirrors on the
**chore track** — no version bump, no CHANGELOG, no tag.

### Repository layout (npm workspaces)
`apps/web` (viewer, Vite's root) and `apps/server` (ws server) are **siblings** — neither app is
nested inside the other, and neither owns a top-level `src/`. Shared code lives in
`packages/shared` and is imported by package name (`@codeblox/shared/*`), never by a relative path
crossing an app boundary. `clients/codeblox` is the Go CLI and builds to `clients/codeblox/bin/`;
`dist/` is the browser build only and must never receive a CLI binary.

### `integration = trunk`
Single operator, agent-driven. Commits and release tags land directly on `main`; the base's
branch guards (§7b guard 1) are inert in trunk mode. Escalate to a short-lived branch only for
risky work, merging before the release.

### There are two version sites
`package.json`'s `"version"` is the source of truth, but the Go CLI carries its own
`command.Version` constant in `clients/codeblox/internal/command/dispatch.go`. A release must bump
**both**. It drifted once already (the CLI still said `0.3.0` at v0.4.0), and it matters more than it
looks: the skill's `resolve_codeblox.py` runs `codeblox version` as its health check, so a stale
constant misreports which binary is in use.

### Version bump baseline
`v0.2.0` is the baseline release covering the pre-tracking work (Phases 1–2, built before this
tracking structure existed). Phase and item ids therefore start allocating at `P-3` / `I-1` / `F-1`.
