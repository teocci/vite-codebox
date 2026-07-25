---
name: dev-phase-lib
description: Shared code library for the dev-phase-* skill family — NOT invoked directly. It ships `tracklib.py` (tracking-config loader, PLAN.md parser, markdown-table engine, CHANGELOG/version/git helpers), which the dev-phase-start / dev-phase-status / dev-phase-workflow / dev-phase-complete scripts import via a uniform bootstrap. There is nothing to run here; skip it when picking a skill to invoke.
---

# dev-phase-lib

The dev-phase-* family's **single shared code library**. This is a code home, not a workflow — there is
no command to run and no reason to invoke this skill. The `dev-phase-*` scripts import from it.

## What it holds

- `scripts/tracklib.py` — the one canonical copy of the family's shared helpers (config/paths loader
  reading `docs/conventions/tracking.md`, `PLAN.md` parsing, the generic markdown-table read/edit
  engine, `CHANGELOG`/version/git utilities). It previously existed as four byte-identical copies,
  one per dev-phase-* skill; it now lives here once. The git helpers are **read-only** by design
  (`git_porcelain`, `git_branch`, `git_ahead_behind`, `git_latest_tag`) — every git *mutation* (branch/merge/tag/push/
  worktree) stays in the SKILL.md runbooks, never in a script. Branch/integration policy keys
  (`release_branch`, `integration`, `concurrency`) load from the same bindings block.

## How consumers import it (uniform bootstrap)

Every consumer script lives two levels below the directory that holds all the sibling `dev-phase-*`
skill dirs — the deployed `.claude/skills/` when installed flat, or the `dev-phase/` family folder in
the source repo — so `parents[2]` is that container in either layout. A consumer adds this block
before importing — copy it verbatim; do **not** duplicate `tracklib.py` itself:

```python
# scripts live at <container>/<skill>/scripts/ → parents[2] is the container of the sibling skill dirs
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dev-phase-lib' / 'scripts'))
import tracklib as tl  # noqa: E402
```

`# noqa: E402` suppresses "import not at top of file" — the import must follow the `sys.path.insert`.
The insert adds the *directory*, so any future module placed in `dev-phase-lib/scripts/` is importable
off the same line without extra bootstrap. This is `__file__`-relative and zero-install (no package
to `pip install`); the library travels with its consumers, so copy the family, not one skill dir.

See `.claude/rules/15-skills.md` and `.claude/rules/07-module-organization.md` for how the skill
rules apply to a shared-library skill like this one.
