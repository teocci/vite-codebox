---
name: dev-phase-workflow
description: Orchestrate the phase lifecycle and own execution sequencing. Detects state via dev-phase-status, suggests execution order over the dependency DAG, advances the NEXT cursor to the next unblocked phase(s), and routes to dev-phase-start / dev-phase-complete. Use when the user says "NEXT", "what's next", "suggest order", "run the workflow", or "continue" — the entry point after a plan is approved and the handler for NEXT. Holds the reusable base conventions.
---

# dev-phase-workflow

The router and sequencing engine for the `dev-phase-*` family. It never edits detail/index files —
it reports, sequences, and moves the `PLAN.md` cursor, delegating mutation to the other skills.

**Conventions hub:** the reusable base lives here in `references/conventions.md`; every `dev-phase-*`
skill reads it, then applies project overrides from `docs/conventions/tracking.md`.

**Shared library:** the scripts import `tracklib` from the `dev-phase-lib` skill via a uniform bootstrap
— see `../dev-phase-lib/SKILL.md`.

## Report first, then act
1. **Read state** (read-only):
   ```bash
   $VENV/python .claude/skills/dev-phase-status/scripts/status.py
   ```
2. **Route** by the situation (first match wins):

   | Situation | Action |
   |---|---|
   | Work is **not a product iteration** (tooling / `.claude/` / meta-docs / CI) | → **chore track**: commit plainly, no `dev-phase-complete` (below) |
   | No active plan / user approved a plan / "start" | → **branch guard** (branch mode): if on `<RELEASE_BRANCH>`, create the `feat/*` branch first (§7b); then run **`dev-phase-start`** to scaffold |
   | Work is discovered **while a plan is active** (a second plan) | → run **`dev-phase-start`** again: it appends the new group and never touches the existing rows. Use `depends` to make it wait on a current phase, `defers` to make current phases wait on it (§6.5) |
   | User asks "where/status" | → run **`dev-phase-status`** (report only) |
   | User wants to finalize/release a worked phase | → run **`dev-phase-complete`** (release integrates to `<RELEASE_BRANCH>` — §7b) |
   | **NEXT** and the just-worked phase is finalized | → **advance** (below) |
   | **NEXT** but the current phase closes a release group and isn't `released` | → **refuse**; point at `dev-phase-complete` Part B |
   | All plan rows `released` | → report plan complete; **drain-branch**: the branch is already integrated per release — delete the merged `feat/*` branch + prune any worktree (§7b), then reset `PLAN.md` to the `No active plan.` stub. `dev-phase-start` **refuses** to scaffold on a fully-released ledger until this is done |

## Release track vs chore track (route before finalizing)
Before treating any work as a release, apply the decision rule (base conventions §6b):
*"Would this appear in product release notes, or change shipped behavior?"*
- **Yes → release track:** it's a phase — use `dev-phase-complete`.
- **No → chore track:** do **not** run `dev-phase-complete` (it would wrongly bump the version + tag).
  Commit directly with a Conventional Commit — `chore:` / `docs:` / `ci:` / `build:` / `refactor:`
  / `test:`. **Everything under `.claude/` (skills, `rules/`, `settings.json`, hooks, commands) is
  chore-track** → `chore(...)`; meta docs → `docs`; `.github/**` → `ci:`. No version bump, no
  CHANGELOG, no RELEASE.md row, no tag. Coherence stays green (chore commits don't touch the
  version/CHANGELOG).

## Sequencing (the order engine)
Use `order.py` for both plan-mode ordering and NEXT selection:
```bash
$VENV/python .claude/skills/dev-phase-workflow/scripts/order.py --suggest   # full order as waves
$VENV/python .claude/skills/dev-phase-workflow/scripts/order.py --next      # phases ready now
```
- **In plan mode** (`--suggest`): propose an execution order. A wave with more than one phase is
  parallelizable — those phases are independent and can run in **separate sessions**.
- **On NEXT** (`--next`): the ready set is phases whose dependencies are all `done` and that aren't
  done yet. Guard: the just-worked phase must be finalized (`PLAN` `done`, tree clean) before
  advancing. If several phases are ready and independent, tell the user they can run in parallel.

## The NEXT loop (why it survives sessions)
The cursor is **not** in conversation memory — it is re-derived from `PLAN.md` every time
(topmost non-`released` row whose deps are all `done`). So NEXT works across new sessions,
compaction, and interleaved commands. Cadence is the `Release` grouping in `PLAN.md`, decided once
at scaffold and re-read each time — nothing to remember.

## Worked scenario (per-phase cadence: P-15[I-5] → P-16[I-6] → P-17[I-7,F-4])
```
approve → dev-phase-start (scaffold PLAN.md)
work I-5 → dev-phase-complete A+B → v0.3.0 tagged
NEXT → order.py --next → P-16 ready → implement I-6
work I-6 → dev-phase-complete A+B → v0.4.0
NEXT → P-17 ready → implement I-7 + F-4
work both → dev-phase-complete (Part A twice, Part B once) → v0.5.0 (F-4 inherits the minor)
NEXT → no phases left → plan complete → reset PLAN.md
```

## Branch & concurrency (§7b — `integration = branch`, `concurrency = hybrid`)
- **Plan-start branch guard:** a plan never starts on `<RELEASE_BRANCH>`. If on it, create the
  plan's `feat/*` branch first (or a worktree for a parallel session) — `dev-phase-start`'s scaffold
  refuses on `<RELEASE_BRANCH>`.
- **Release = integration:** each `dev-phase-complete` Part B integrates the finished phase(s) into
  `<RELEASE_BRANCH>` and tags there (`main` stays the released truth). So by plan-complete the branch
  is already drained → delete it + prune any worktree, then reset `PLAN.md`.
- **Mid-plan hotfix** (a bug that can't wait for the plan): don't derail the plan branch. Isolate the
  fix on `<RELEASE_BRANCH>` in a **worktree** so the plan's working tree stays put, release it there,
  then the plan branch pulls `<RELEASE_BRANCH>` to absorb the fix (re-plan between phases if the
  version moved). Layout-agnostic — `git worktree add <path> <branch>` works on the current flat repo
  today; each worktree needs its own venv (see `tracking.md`). For the worktree/merge/cleanup
  mechanics use `superpowers:using-git-worktrees` / `finishing-a-development-branch` when available;
  otherwise the runbook here is self-contained.

## Superpowers switch & subagents
When the superpowers skills are installed, **prefer** them for the heavy steps; when they are not,
the embedded runbooks here stand alone.

- **Plan** → `superpowers:brainstorming` before scaffolding.
- **Implement** → `superpowers:test-driven-development` drives each change.
- **Verify** → `superpowers:verification-before-completion` / `requesting-code-review`.
- **Branch/worktree/release cleanup** → `superpowers:using-git-worktrees` /
  `finishing-a-development-branch` (§7b).

Reference sub-skills **by name** (e.g. "use superpowers:test-driven-development"), never with
`@`-links — those force-load and burn context. **When you dispatch a subagent, name the cheapest
capable model:** an omitted model inherits this session's (often most expensive) model, silently
defeating the point of delegating.

## Notes
- This skill routes and sequences; its **scripts** never run git (`order.py` only parses `PLAN.md`).
  Release git (commit/tag/push/integrate) is `dev-phase-complete`; branch-create and the plan-complete
  drain/prune are short runbook steps the model runs — never a script (§7b).
- Direct use of `dev-phase-start` / `dev-phase-status` / `dev-phase-complete` is fine; the orchestrator is a
  convenience entry point, not a mandatory chokepoint.
