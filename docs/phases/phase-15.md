# Phase 15 — Viewer ops — a third op category, published and relayed

- **Phase ID:** 15
- **Version:** 0.9.0
- **Date:** 2026-07-28
- **Tests:** 542
- **Status:** ✅ DONE (542 tests; live-verified).

## Objective

Give the protocol a vocabulary for directing presentation. Five explicit ops — `view`, `reframe`,
`rotate`, `grid`, `hud` — in a third category the server relays to every viewer and never stores,
plus the shared `VIEWS` table that lets an out-of-range view be refused instead of silently ignored.
Nothing moves on screen yet; that is P-16. Carries I-12.

## What was built

A third op category. `VIEWER_OPS` (`view`, `reframe`, `rotate`, `grid`, `hud`) sits beside
`PART_OPS` and `CONTROL_OPS` in `protocol.js`, with `isViewerOp` as the single routing predicate the
server and the viewer's local path both need. The server collects them into a `viewer` array and puts
that on the **broadcast** only — a viewer op is relayed, never stored, and the sender sees it via the
broadcast it is already part of.

`VIEWS` moved to `packages/shared/views.js` so `protocol.js` can range-check `n` against
`VIEW_COUNT`. That is the whole reason for the move: while the table was module-scoped inside
`CameraDirector.js`, `view 7` could only be a silent no-op, which to a blind agent is
indistinguishable from success.

Two details are load-bearing rather than incidental. The `viewer` array is **not** reset inside the
`clear` arm the way `added`/`removed` are — a clear erases the world but does not make "look from
view 1" moot. And the ordering rule now lives in the `protocol.js` header: viewer ops apply after the
world diff regardless of batch position, so `[{view:1}, box, clear]` lands as `clear → box → view`.

Nothing moves on screen yet — that is P-16.

## Files changed

| File | Change |
|---|---|
| `packages/shared/views.js` | New — the `VIEWS` table + `VIEW_COUNT`, dependency-free |
| `packages/shared/protocol.js` | `VIEWER_OPS`/`isViewerOp`, `isBool`, five schema rows, five validate arms, widened unknown-op gate, ordering rule in the header |
| `apps/web/src/viewer/CameraDirector.js` | Imports `VIEWS` instead of defining it |
| `apps/server/commands.js` | Collects viewer ops; survives `clear` |
| `apps/server/createServer.js` | Relays `viewer` on the broadcast, not the ack |
| `tests/shared.test.js` | 9 new cases |
| `tests/server.test.js` | 5 new cases |

## Verification

`npm test` → 8 files, 109 tests passed (14 new). `npm run build` → clean, confirming the new shared
module resolves in the browser build and not only under vitest.
