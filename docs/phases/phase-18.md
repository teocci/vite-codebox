# Phase 18 — The skill learns to direct the camera

- **Phase ID:** 18
- **Version:** (pending)
- **Date:** (pending)
- **Tests:** (pending)
- **Status:** 🚧 IN PROGRESS

## Objective

Teach the skill the viewer ops — the `world.py` no-geometry allowlist (keeping F-2's raise for
anything unrecognised) and a `SKILL.md` section covering both the imperative and declarative paths.
Lands last, so the documentation describes only behaviour that already exists. Carries I-15.

## What was built

`world.py` learned the five viewer ops as a second no-geometry set beside `CONTROL_OPS`, unioned into
`NO_GEOMETRY_OPS`, which is what `aabb()` now reads. The split rather than one widened frozenset is what
keeps this hand-written mirror comparable to `protocol.js` set-for-set.

No new script, and none was needed: `build.py`'s `expand_part` already passes any dict carrying an `op`
through verbatim, and `check_stage`'s "at least one part" is satisfied by a raw op — so a plan could express
`{"op":"view","n":1}` in a stage the moment `aabb()` stopped raising on it. What was missing was purely the
measurement rule and the documentation.

`SKILL.md` gained §7 "Direct the camera": the five ops, `codeblox view` as the imperative path and a plan
stage as the declarative one, the rule that `reframe`/`grid`/`hud`/`rotate` act on the world as it stands
when their stage lands while a held `view` is better set first, and how to read a batch that adds nothing.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/scripts/world.py` | `VIEWER_OPS`, `NO_GEOMETRY_OPS`; `aabb()` reads the union |
| `.claude/skills/codeblox-builder/SKILL.md` | §7 "Direct the camera" |
| `.claude/skills/codeblox-builder/tests/test_world.py` | union parametrisation, set disjointness, unlisted-viewer-op raise |
| `.claude/skills/codeblox-builder/tests/test_build.py` | viewer op does not move the measured extent; a viewer-only stage is a stage |
| `.codex/`, `.agents/` mirrors | propagated, chore track |

## Verification

267 pytest passed / 1 skipped (9 new); `npm test` 126 green. Live against the running server: the
unknown-op raise still fires at exit 5, `view 99` is refused by the server at exit 6, and a two-stage plan
with a viewer-op review stage landed with the geometry stage reporting ids and the review stage reporting
none. Full detail, including the `SKILL.md` claim the live run corrected, in [I-15](../improvements/I-15.md).
