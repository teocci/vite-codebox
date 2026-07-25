# I-5 — A staged build workflow for `codeblox-builder`

- **Item ID:** I-5
- **Version:** unreleased
- **Date:** 2026-07-26
- **Tests:** 144 skill pytest (40 added in `tests/test_build.py`), 1 skipped
- **Status:** complete, awaiting a release.
- **Related work:** builds on I-2 (the exit taxonomy `build.py` branches on) and the `submit.py`
  bounds gate it generalises. Touches no shipped artifact — skill only.

## Objective

The skill had a *pipeline* and no *workflow*. `world.py → shapes.py → submit.py` built a structure as
one flat batch, reported one line, and said nothing about the order things land in. Three gaps, one
of which is a correctness problem rather than an ergonomic one.

**The gate did not cover the build.** `submit.py` dry-runs the batch it was handed and nothing else.
A misspelled material in the last stage of a five-stage build was therefore invisible until the
first four had already landed — and there is no partial undo, because `remove` takes an id, not a
region. The only recovery was `clear` and start over. The skill's own guidance
("submit them as separate batches") actively steered into this.

**Build order was invisible to the skill and visible to the audience.** `DropAnimator` drops each new
part from `DROP_HEIGHT` blocks up over `DROP_MS`, staggered `STAGGER_MS` per part, and settled parts
never re-animate. So **every submitted batch is one animation beat**. A forty-part castle sent flat
lands as one undifferentiated shower; the same castle in five stages reads as something being built.
Order is choreography, and nothing in the skill said so.

**No progress.** One `sent 40 command(s)` line for the whole thing.

## The correction that shaped the design

The originating sketch had a *carve* step — "remove box for openings". **This engine cannot carve.**
`applyBatch` resolves `remove` by `cmd.id`, and geometry is scaled parts rather than voxels, so there
is no boolean subtraction. Openings are made by **composition**: parts arranged around the gap, which
is what `shapes.shell` already does with its inset walls. The build order in `SKILL.md` says so
explicitly, and `Guardrails` now carries "there is no carving" and "there is no partial undo" —
the second being the reason the up-front gate matters at all.

## Approach

A plan is one JSON object of named stages; a part is either a **shape call** expanded through
`shapes.py` or a **raw command** passed through untouched. `build.py` then runs a fixed order:

```
1. load plan          malformed / no stages / unnamed stage  -> exit 2
2. expand all stages  error names the stage AND the part     -> exit 2
3. bounds-check all   per stage, nothing sent                -> exit 5
4. one exec --dry-run over the whole flattened plan          -> exit 5/6
   --dry-run stops here
5. per stage: send -> progress line -> pace
```

Steps 3 and 4 are the deliverable: they see stage 5 while stage 1 is still unsent, which is
structurally impossible for `submit.py` — it is a stdin-to-one-batch pipe. **A plan either builds or
nothing moves.**

### Reuse, not reimplementation

- Shape expansion calls `shapes.shell` / `stairs` / `arch` / `bridge` directly. No geometry is
  duplicated; `build.py` contains no coordinate arithmetic at all.
- Arguments bind through `inspect.signature`, so the accepted keys **cannot** drift from the
  functions, and an unknown key reports what the generator does accept instead of raising a bare
  `TypeError`. `-` and `_` are both accepted, so a plan key matches its CLI flag.
- Bounds arithmetic stays `world.out_of_bounds`. `build.py` has its own `check_bounds` only to change
  the *reporting*: `submit.check_bounds` indexes one flat batch, which across five stages says
  "command 32" — true, and useless. The per-stage version says `stage 2 (sky) command 0 (box): …`.

### The drop constants are copied, and the copy is pinned

`DROP_MS` and `STAGGER_MS` live only in `apps/web/src/engine/DropAnimator.js` — not in
`packages/shared`, not in the published contract — so Python cannot read them at runtime. They are
copied into `build.py` with a comment naming the source, and
`test_the_drop_constants_still_match_the_viewer` reads that file and fails on drift. It skips when
the engine is not alongside, so the `.agents/` mirror stays runnable on its own.

Promoting them into `packages/shared` would be the better fix and was **not** done: it is an engine
change, and this item is scoped to the skill.

### What was deliberately not built

An **undo ledger** (stage → ids, plus an `undo` mode) was considered and rejected. It would be a
second source of truth for world state in a project whose locked invariant is that the server is
authoritative — a file on disk making claims a `clear`, another agent, or the viewer's offline
fallback can invalidate without it knowing. Its competitor is `clear` + re-run, which for a
pre-validated declarative plan is one command and deterministically identical; undo only wins when
the world holds work from outside the plan, which is exactly when the ledger is most likely stale.
It also would not preserve the visual state, since re-placing re-drops. `--only NAME` against a
cleared world covers the iterate-on-one-stage case. Additive later if it earns its keep.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/scripts/build.py` | **New.** Plan loading, shape expansion, the whole-plan gate, staged send, pacing, progress. |
| `.claude/skills/codeblox-builder/tests/test_build.py` | **New.** 40 tests, including the two drift guards. |
| `.claude/skills/codeblox-builder/SKILL.md` | `The pipeline` → `The workflow`; new §3 *Plan the stages* (build order + plan format + worked example) and §4 *Build*; §5 folds the generators and the `submit.py` quick path together. `Compose` now orders the composition; `Guardrails` gains no-carving and no-partial-undo. Frontmatter description reduced to triggering conditions. |
| `.agents/skills/codeblox-builder/**` | Mirror, kept byte-identical. |

### Why the description changed

It summarised the workflow ("resolve the CLI, discover the live contract, generate exact block
coordinates, and submit a validated batch"). A description that summarises a workflow becomes a
shortcut the model follows *instead of* reading the body — which is precisely the failure this item
exists to fix, since the body is where the staging now lives. It is now triggering conditions only.

## Verification

| Check | Result |
|---|---|
| skill pytest | 104 → **144 passed**, 1 skipped (the pre-existing Windows `os.access(X_OK)` skip) |
| Drift guard, generators | `shapes.build_parser()` subcommands == `build.SHAPES` |
| Drift guard, animation | `DropAnimator.js` reports `DROP_MS=350`, `STAGGER_MS=18`; matches `build.py` |
| Gate, offline | A plan whose *last* stage leaves the world exits **5**, names `stage 2 (sky)`, sends nothing |
| Live dry run | `castle.json` → "32 command(s) across all stages are valid and in bounds, nothing sent", exit 0 |
| Live build | Five stages landed in order, ids 1..31, paced 350/440/548/548 ms |
| Live `--from` / `--only` / `--json` | Resume and single-stage re-send both land correctly |

### One bug the unit tests did not catch

The live `--from 4` run printed **`stage 4/2`** — the progress denominator was the *selected* stage
count rather than the plan's. Fixed to count against the plan, with
`test_progress_counts_against_the_plan_not_the_selection` added, since the suite was green while it
was wrong.

**Not exercised live: the mid-build failure path.** Every stage is validated before the first is
sent, so making a stage that passes validation and then fails on send is not arrangeable without
killing the server mid-run. It is covered by `test_a_failure_part_way_names_what_already_landed`,
which asserts the message names the landed stages, their ids, and the `--from N` to resume with.
