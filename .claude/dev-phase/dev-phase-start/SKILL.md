---
name: dev-phase-start
description: Scaffold the tracking structure for an approved plan — allocate phase/item ids, create detail stubs, add index rows, and write the PLAN.md ledger with dependencies and release grouping. Use when a plan is approved and the user says "scaffold this plan", "start these phases", "set up tracking", or "begin implementation". Run right after a plan is approved, before implementation. Docs-only; never commits or bumps the version.
---

# dev-phase-start

Turn an approved plan into tracking structure. Deterministic id-allocation, stub creation, index
rows, and the `PLAN.md` ledger run in `scripts/scaffold.py`; you supply the plan spec and then fill
the stub bodies.

**Read first:** base conventions `../dev-phase-workflow/references/conventions.md` and project overrides
`docs/conventions/tracking.md` (the hierarchy, phase-sizing heuristic, and templates).

**Shared library:** the scripts import `tracklib` from the `dev-phase-lib` skill via a uniform bootstrap
— see `../dev-phase-lib/SKILL.md`.

## Steps
1. **Assemble the plan spec** from the approved plan. Decompose the work into
   **context-window-sized phases** (conventions §2), each bundling one or a few items. Capture
   dependencies and release grouping (the cadence). Ask the user only if grouping/deps weren't
   stated. Spec shape (JSON):
   ```json
   {
     "approved": "<YYYY-MM-DD>", "branch": "<branch>", "cadence": "per-phase | batched",
     "phases": [
       {"title": "…", "depends": [], "release": "R1",
        "items": [{"kind": "improvement|fix", "title": "…", "summary": "one-line",
                   "objective": "…", "related": "siblings …"}]}
     ]
   }
   ```
   `depends` entries are 0-based indices into this spec's `phases` array.
2. **Branch guard** (`integration = branch`; conventions §7b guard 1) — a plan never starts on
   `<RELEASE_BRANCH>`. If HEAD is the release branch, create the plan branch first (and record it as
   the spec `branch`):
   ```bash
   git switch -c feat/<slug>          # or, for a parallel session: git worktree add ../<slug> -b feat/<slug> main
   ```
   `scaffold.py` **refuses** (exit 2, structured error) if run on `<RELEASE_BRANCH>` in `branch`
   mode — it never creates the branch itself (that's this runbook step). In `trunk` mode there is no
   guard. Each new worktree needs its own venv (see `tracking.md`).
3. **Run the scaffold** (writes stubs + index rows + `PLAN.md`; allocates next-free ids):
   ```bash
   $VENV/python .claude/skills/dev-phase-start/scripts/scaffold.py --spec <spec.json>
   ```
   Preview first with `--dry-run` to see the ids and files it will create.
4. **Fill the stub bodies** — for each created detail file, write the Objective/Approach (or
   Symptom) from the plan. Leave frontmatter `Status: 🚧 IN PROGRESS` / `Version: (pending)`;
   `dev-phase-complete` stamps those at finalize/release.
5. **Report** the scaffolded phases and which are unblocked to start (run `dev-phase-workflow`'s
   `order.py --suggest` for the execution order). **Do not** commit, bump the version, or touch
   `CHANGELOG.md` — scaffolding is docs-only.

## Verification
- [ ] `PLAN.md` lists every phase with items, `Depends`, `Release`, and `pending` status
- [ ] Each phase/item has a detail stub and an in-progress index row
- [ ] `PROGRESS.md` phase table gained a `planned` row per phase
- [ ] Not on `<RELEASE_BRANCH>` in `branch` mode (plan branch created first — a manual pre-step)
- [ ] `scaffold.py` did no version bump, no `CHANGELOG.md` edit, no git (docs-only; the script never
      creates the branch)

## Notes
- Ids are allocated next-free by scanning the indexes; never reuse an id.
- If a plan changes mid-flight, re-running scaffold allocates *new* ids — prefer editing `PLAN.md`
  and the stubs directly for small adjustments.
