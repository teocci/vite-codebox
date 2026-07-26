# Phase 10 — SKILL.md: the authoring rule, the shape vocabulary, and the real part cost

- **Phase ID:** 10
- **Version:** 0.7.0
- **Date:** 2026-07-27
- **Tests:** 483
- **Status:** ✅ DONE (483 tests; live-verified).

## Objective

The skill's own worked examples taught the 50x error, and its cost guidance steered the model away from the many-part approach curved forms need.

## What was built

One item, I-9 — see `docs/improvements/I-9.md` for the design and the reasoning.

`SKILL.md`'s two worked examples were replaced because they *demonstrated* the 50x error rather than merely failing to warn about it: an 80 cm castle and a 16 cm bridge deck. With P-9's gate live, leaving them meant the documentation led the model into a refusal the documentation could not explain. The replacement example was built against a running server before being written down.

The cost guidance was replaced because it was false. The renderer keeps one instanced mesh per *(geometry kind x render family)* and colours instances individually, so the whole world is bounded at twenty draw calls at any part count — not "40x the cost" for forty boxes. The advice inverts accordingly: part count is cheap, and the curved and raked forms this phase adds need many parts.

Five generators close the gap between what the skill told the model to do and what it gave it to do it with: `wheel`, `taper`, `dome`, `pane` and `window`. `pane` is the load-bearing one — nothing in this engine is ever rotated, so a raked surface has to be a staircase of thin slabs, and the rebuilt Tesla spends 178 of its 305 parts stepping exactly that by hand.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/SKILL.md` | The six wrong or missing sites, plus a new step for declaring the subject and a documented generator table |
| `.claude/skills/codeblox-builder/scripts/shapes.py` | `tube`/`ellipsoid` emitters and the five new generators |
| `.claude/skills/codeblox-builder/scripts/build.py` | The new generators registered so plans can reach them |
| `.claude/skills/codeblox-builder/tests/test_shapes.py` | 20 cases over the five generators |

## Verification

466 tests: 74 vitest, 112 Go unit, 24 Go e2e, 256 pytest (`codeblox-builder`, +1 skipped) — the pytest suite grew by 46 across P-9 and P-10. The `dev-phase` family's 54 pytest are chore-track tooling, counted separately.

Live-verified three times: a `rotunda` (`wheel`/`taper`/`dome`), a `shelter` (`pane`/`window`), and the pavilion that is now `SKILL.md`'s example. Every command in the file was executed before being documented, which is what caught the `pane` default emitting 116 parts for one windshield.

## Notes / follow-ups

- `pane`'s default of one slab per block of rise is the finest the grid allows and the most expensive. It is documented as a dial rather than capped, because the right value depends on how close the viewer gets — but it means an unset `--steps` on a large rake is a lot of parts.
- The `.codex/` and `.agents/` mirrors of `codeblox-builder` are now stale by two phases.
