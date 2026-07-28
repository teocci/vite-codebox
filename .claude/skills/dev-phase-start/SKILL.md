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
     "defers": ["P-15"],
     "phases": [
       {"title": "…", "depends": [], "release": "R1",
        "items": [{"kind": "improvement|fix", "title": "…", "summary": "one-line",
                   "objective": "…", "related": "siblings …"}]}
     ]
   }
   ```
   - `depends` — an **int** is a 0-based index into this spec's `phases` array (an earlier phase
     only); a **string** is an existing ledger phase id, e.g. `"P-17"`.
   - `defers` — the reverse edge: existing **pending** phase ids that must now wait for this
     scaffold. Each named row's `Depends` cell gains this run's terminal phases; nothing else in
     the row changes.
   - `release` — **required per phase when a plan is already active.** The `R<n>` default restarts
     at R1 every run and would reopen a group the ledger already owns.
   - `approved` / `branch` / `cadence` are honored on a **fresh** write only. One ledger has one
     header, so an append keeps the existing one and reports a warning if the spec disagrees.

2. **Adding a second plan mid-flight.** Scaffolding while a plan is active is supported and
   additive — the new rows are appended and no existing row is rewritten. Pick the ordering:

   | The new work… | Spec | `order.py --next` then reports |
   |---|---|---|
   | must wait for a current phase | `"depends": ["P-17"]` | the current plan's root |
   | must come **first** (defer the current plan) | `"defers": ["P-15"]` | the new group's root |
   | is independent | neither | **both** roots, flagged parallelizable |
3. **Branch guard** (`integration = branch`; conventions §7b guard 1) — a plan never starts on
   `<RELEASE_BRANCH>`. If HEAD is the release branch, create the plan branch first (and record it as
   the spec `branch`):
   ```bash
   git switch -c feat/<slug>          # or, for a parallel session: git worktree add ../<slug> -b feat/<slug> main
   ```
   `scaffold.py` **refuses** (exit 2, structured error) if run on `<RELEASE_BRANCH>` in `branch`
   mode — it never creates the branch itself (that's this runbook step). In `trunk` mode there is no
   guard. Each new worktree needs its own venv (see `tracking.md`).
4. **Run the scaffold** (writes stubs + index rows + the `PLAN.md` rows; allocates next-free ids):
   ```bash
   $VENV/python .claude/skills/dev-phase-start/scripts/scaffold.py --spec <spec.json>
   ```
   Preview first with `--dry-run` — it reports `plan_mode` (`fresh` or `append`), the ids and files
   it will create, and surfaces every refusal without writing.
5. **Fill the stub bodies** — for each created detail file, write the Objective/Approach (or
   Symptom) from the plan. Leave frontmatter `Status: 🚧 IN PROGRESS` / `Version: (pending)`;
   `dev-phase-complete` stamps those at finalize/release.
6. **Report** the scaffolded phases and which are unblocked to start (run `dev-phase-workflow`'s
   `order.py --suggest` for the execution order). **Do not** commit, bump the version, or touch
   `CHANGELOG.md` — scaffolding is docs-only.

## Verification
- [ ] `plan_mode` in the result is the one you expected (`append` whenever a plan was already active)
- [ ] Every **newly scaffolded** phase has a `PLAN.md` row with items, `Depends`, `Release`, `pending`
- [ ] Pre-existing rows are unchanged — same `Status` and `Version`, and the ledger header still
      records the original `Approved` / `Branch` / `Cadence`
- [ ] Each row named in `defers` gained the new group in its `Depends` cell, and nothing else
- [ ] `order.py --next` offers the phases you intended (see the ordering table in step 2)
- [ ] Each phase/item has a detail stub and an in-progress index row
- [ ] `PROGRESS.md` phase table gained a `planned` row per phase
- [ ] Not on `<RELEASE_BRANCH>` in `branch` mode (plan branch created first — a manual pre-step)
- [ ] `scaffold.py` did no version bump, no `CHANGELOG.md` edit, no git (docs-only; the script never
      creates the branch)

## Notes
- Ids are allocated next-free from the indexes **and** the ledger; never reuse an id.
- **Re-running scaffold on an active plan is safe** — it appends and never rewrites an existing row,
  so a second plan can be captured without losing the first. It allocates *new* ids for the new
  phases; to change a phase already in the ledger, edit that row and its stub directly.
- `scaffold.py` refuses (exit 2, writes nothing) rather than replace a ledger it cannot read
  confidently: a fully-`released` plan (run the §7b drain and reset to the stub first), a
  fragmented or malformed table, an unknown `depends`/`defers` id, a non-`pending` defer target, a
  reused release tag, or a spec that would create a dependency cycle.
