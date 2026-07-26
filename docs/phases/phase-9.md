# Phase 9 — The scale gate — declared subject dimensions, checked before send

- **Phase ID:** 9
- **Version:** (pending)
- **Date:** (pending)
- **Tests:** (pending)
- **Status:** 🚧 IN PROGRESS

## Objective

Make 1:1 the outcome rather than something the model must remember. Every man-made build in builds/ landed at 15-26% of true size and nothing noticed.

## What was built

One item, I-8 — see `docs/improvements/I-8.md` for the design and the reasoning.

A plan may now declare `subject.mm`, the real size of the thing it builds. `build.py` measures the expanded plan's own AABB and refuses a deviation **before the first block is sent**, which is the only useful moment: `remove` takes an id, not a region, so a wrongly-scaled build cannot be partially undone. The per-axis ratio triple separates a uniform scale error, which `dims.py fit` repairs mechanically, from a proportion error, which it must not touch — one factor cannot fix three ratios, and applying one anyway produces a correctly-sized wrong shape that then passes the gate. A subject too large for the world is reported separately, naming the `world.extent` to raise rather than suggesting a smaller build.

The new `dims.py` is how a declaration becomes coordinates in the first place, and how a plan that came out wrong gets repaired without being rewritten by hand. It scales both corners of every part and derives the size from them, because rounding `at` and `size` independently opens a one-block seam at every joint.

Supporting that, the metre is now visible everywhere the block already was: `world.digest` derives `blocksPerMetre` from the contract, `doctor.py` states it on the rung that already had the contract, and each stage's progress line reports what it landed in metres. Nothing writes the block size down.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/scripts/build.py` | Subject validation, `plan_aabb`, `check_scale` and its two failure envelopes, metres in `stage_line` |
| `.claude/skills/codeblox-builder/scripts/dims.py` | Completed and corrected: `to-blocks`, `fit`, `anchors`; the inherited `factor` defect fixed |
| `.claude/skills/codeblox-builder/scripts/world.py` | `blocks_per_metre` derived; reported in the digest and the rendered view |
| `.claude/skills/codeblox-builder/scripts/doctor.py` | The world rung carries the metre label it had been dropping |
| `.claude/skills/codeblox-builder/tests/` | `test_dims.py` and `test_doctor.py` are new; `test_build.py` and `test_world.py` extended |

## Verification

420 tests: 74 vitest, 112 Go unit, 24 Go e2e, 210 pytest (`codeblox-builder`, +1 skipped) — the pytest suite grew by 48. The `dev-phase` skill family's 54 pytest are chore-track tooling and counted separately, as before.

Live-verified against a running server: a real Model S declaration refused at exit 5 with the uniform-miss classification, repaired by `dims.py fit`, then built — 37 parts in 5 stages, 4.96 m in the world. The live run caught a fixed-width metre column that printed `3.26 m620ms`; it is now width-yielding and pinned by a test.

## Notes / follow-ups

Two things surfaced while verifying this phase, neither in its scope:

- `world.fetch(refresh=True)` passes `--refresh` to `codeblox info`, which does not accept it (`flag provided but not defined: -refresh`). A refresh is therefore a usage error and `doctor.py` can silently report a stale cached contract — the cache had to be deleted by hand to re-fetch. Wants its own fix item.
- The running ws server was **stale** while this phase was verified: a fresh contract fetch published only 8 ops, without P-8's `ellipsoid` and `tube`, though both are committed in `packages/shared/protocol.js`. Resolved by a restart during P-10, where both ops were then live-verified. The lasting lesson is diagnostic: from the outside a stale server looks exactly like a stale cache, and the `--refresh` defect above is what makes the two hard to separate.
- The plans in `builds/` predate P-8's ops and all sit at 15-26% of true size. They were deliberately left undeclared: they are gitignored working files, stale for reasons unrelated to this phase, and declaring subjects would make all five refuse to build until fitted.
