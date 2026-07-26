# Phase 12 — A build is a thing, to the skill and to the viewer

- **Phase ID:** 12
- **Version:** 0.7.0
- **Date:** 2026-07-27
- **Tests:** 483
- **Status:** ✅ DONE (483 tests; live-verified).

## Objective

Retroactive. This phase carries no new work — it is the tracking row for I-5 and I-6, which were
implemented and committed at `8c99d21` (after the `v0.6.0` tag) outside the phase structure and so
had no route to a version. See `docs/PLAN.md` handoff note 3 for why the row was allocated after
the fact and why it ships in R2 rather than as its own release.

The two items are one idea in two halves. I-5 gave `codeblox-builder` a *workflow* where it had
only a pipeline: a declarative stage plan, validated end to end before the first block is sent.
I-6 made the resulting boundary visible to the viewer, which until then saw an undifferentiated
stream of parts and could not know which ones were the new build.

## What was built

- **I-5** — `build.py`: a plan is named stages of shape calls or raw commands; every stage is
  expanded and bounds-checked, and the whole flattened plan is dry-run, *before* stage 1 is sent.
  A plan either builds or nothing moves — which matters because `remove` takes an id, so there is
  no partial undo. Stages then land beat by beat, paced off the real settle time, since each batch
  is one `DropAnimator` beat. Skill-only; no shipped artifact changed. Detail:
  `docs/improvements/I-5.md`.
- **I-6** — a field-less `build_begin` control op through `packages/shared/protocol.js`, relayed by
  the server and sent by `build.py` ahead of stage 1. `World` groups the build's ids; `Viewer`
  frames that sphere instead of every part in the world. Zero Go changes — the CLI is
  schema-driven, so it picked the op up on a server restart. Detail:
  `docs/improvements/I-6.md`.

## Files changed

| File | Change |
|---|---|
| `packages/shared/protocol.js` | `build_begin` through `CONTROL_OPS`, `OP_SCHEMA`, `validate` |
| `apps/server/commands.js`, `apps/server/createServer.js` | relay `buildBegin` in the diff and the ack; no store mutation |
| `apps/web/src/engine/World.js` | `onBuildBegin` / `onAdded(ids)` / `boundsOf(ids)`; shared `aabbOf` / `sphereOf` |
| `apps/web/src/viewer/CameraDirector.js`, `Viewer.js` | focus group; `_worldBounds` → `_framedBounds`; `reframe()` drops the focus |
| `apps/web/src/net/WsClient.js`, `main.js` | forward `buildBegin` on both the online and offline paths |
| `.claude/skills/codeblox-builder/scripts/build.py` + `tests/test_build.py` | **New.** The staged workflow and its 40 tests |
| `.claude/skills/codeblox-builder/SKILL.md` | *The pipeline* → *The workflow*; stage planning; no-carving and no-partial-undo guardrails |
| `.gitignore` | `builds/` — the plan working directory, untracked |

## Verification

As recorded in the two detail files at the time of the commit: 68 vitest (9 added) and 150 skill
pytest (6 added, 1 skipped). Live: two plans built back to back into one world, with a stand-in ws
client confirming the second `build_begin` arrives into a populated world and the focus group
accumulates only the new ids.

Not covered by any automated check: the camera motion in a real browser after a human has dragged
the canvas — that link needs a WebGL context and a human glance.
