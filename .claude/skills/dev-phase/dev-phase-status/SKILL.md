---
name: dev-phase-status
description: Read-only status and coherence report for the active plan — phase cursor, per-phase status, unblocked/parallelizable next phases, uncommitted work, unreleased CHANGELOG bullets, current version, and drift flags. Use when the user asks "where are we", "status", "what's in progress", "progress report", or "check coherence". Run any time to see where the work stands. Never mutates.
---

# dev-phase-status

A token-efficient, read-only snapshot of the active plan. Reused by the `dev-phase-workflow` orchestrator
and callable any time. **Mutates nothing.**

**Read first (only if acting on findings):** base conventions `../dev-phase-workflow/references/conventions.md`
and `docs/conventions/tracking.md`.

**Shared library:** the scripts import `tracklib` from the `dev-phase-lib` skill via a uniform bootstrap
— see `../dev-phase-lib/SKILL.md`.

## Steps
1. **Status report** — plan cursor, per-phase status, unblocked/parallelizable next phases,
   uncommitted files, `[Unreleased]` bullet count, current version:
   ```bash
   $VENV/python .claude/skills/dev-phase-status/scripts/status.py            # text
   $VENV/python .claude/skills/dev-phase-status/scripts/status.py --json     # machine-readable
   ```
2. **Coherence (advisory)** — surface drift without failing:
   ```bash
   $VENV/python .claude/skills/dev-phase-status/scripts/check_coherence.py --advisory [--json]
   ```
   (`dev-phase-complete` runs the same check **without** `--advisory` as a hard release gate. Add
   `--json` for one compact machine-readable line: `{"ok",...,"failed",...,"checks":[...]}`.)
3. **Report and point** — summarize; if drift appears (e.g. RELEASE.md ≠ `__version__`, a detail
   file for the current version not `✅ DONE`), name it and point at the skill that fixes it
   (`dev-phase-complete` for finalize/release, `dev-phase-workflow` for advancing). Never edit anything here.

## What the coherence check asserts
`__version__` is semver · `pyproject.toml` has no literal `version=` (dynamic intact) · top
`CHANGELOG` `## [X.Y.Z]` == `__version__` · `RELEASE.md` top row == `__version__` · every detail
file stamped with the current version is `✅ DONE` · **when on `<RELEASE_BRANCH>`**, the latest
reachable tag == `v__version__` (the released-truth invariant, §7b; skipped off the release branch).

`status.py` also reports **branch drift** — when HEAD is off `<RELEASE_BRANCH>`, its ahead/behind
count (an `UNMERGED` marker when the branch has un-integrated commits). This is the report that
surfaces unmerged plan work.

## Notes
- No active plan → `status.py` reports `plan: none active`; that's expected between plans.
- This skill is the observation layer; all mutation lives in `dev-phase-start` / `dev-phase-complete`.
