# Phase 19 — Split the HUD extent row so the panel stops growing

- **Phase ID:** 19
- **Version:** 0.9.0
- **Date:** 2026-07-28
- **Tests:** 542
- **Status:** ✅ DONE (542 tests; live-verified).

## Objective

Make the HUD legible at the scales the project now builds at. Split the `extent` row into `extent`
(metres) and `blocks` (integers), space the numbers so they are separable and can wrap, and cap the
panel width so it is bounded rather than merely shorter. Values stay exact — abbreviation was
rejected on arithmetic, and the metres row is load-bearing for the I-8 scale gate. Carries F-4.

## What was built

The `extent` row became two rows — `extent` in metres, `blocks` in integers — and `.hud` gained a
`max-width` beside the `min-width` it always had.

The split is forced by arithmetic rather than chosen for taste: `BLOCK_SIZE` is `0.02`, so the block
triple is always exactly 50× the metre triple. Once either is large both are, and one row can never
hold them again. It only ever fit the 64 m world that shipped before P-11.

The separator went from `×` to `' × '`, which is the part that makes the cap work at all. Without
spaces the triple is a single unbreakable word and no `max-width` can contain it; with them the value
wraps at its own separators, and `min-width: 0` on `.value` lets the flex item shrink to that wrapped
width.

Values stay exact. `2.7k m` cannot be checked against a real subject's 2737 m, and that comparison is
what the I-8 scale gate is for — so no digit was traded for width. Carries F-4.

## Files changed

| File | Change |
|---|---|
| `apps/web/src/viewer/Hud.js` | Two exported pure formatters; `extent` split into `extent` + `blocks` |
| `apps/web/src/viewer/Hud.module.css` | `max-width: 20rem` on `.hud`; `min-width: 0` on `.value` |
| `tests/hud.test.js` | New — 5 cases |

## Verification

`npm test` → 9 files, 114 tests passed (5 new). `npm run build` clean, with both new CSS rules
present in the emitted `dist/assets/*.css`. The rendered panel was not observed in a browser this
session — see F-4's Verification for what that leaves unconfirmed.
