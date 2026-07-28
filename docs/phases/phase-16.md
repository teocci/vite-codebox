# Phase 16 — The viewer applies agent direction, and an agent-set angle holds

- **Phase ID:** 16
- **Version:** 0.9.0
- **Date:** 2026-07-28
- **Tests:** 542
- **Status:** ✅ DONE (542 tests; live-verified).

## Objective

Make the five ops do something. Route them around the block engine via a new `onViewer` callback on
`WsClient`, turn every toggle into an idempotent setter because an agent cannot read viewer state
back, and add `hold` so an agent-set camera angle is preserved and refit as a build grows rather
than silently disabling the auto-framer for the remaining stages. Carries I-13.

## What was built

Three things, of which the third is the one that changes behaviour rather than plumbing.

**A route around the block engine.** `WsClient` gained `onViewer` beside `onStatus`, fired after
`world.applyDiff`. Threading five presentation ops through `World.applyDiff` was rejected: `World.js`
is the block engine, and it would gain parameters it neither reads nor validates. `buildBegin` is one
wart, not a pattern to extend. Because the callback fires from a single statement, the protocol's
ordering rule — viewer ops apply after the world diff whatever their batch position — lives in one
testable place instead of being emergent.

**Idempotent setters everywhere.** Every toggle got a setter beside it, and the toggle now delegates.
This is forced by the agent being blind: viewer state is not in `world_info` and there is no
read-back channel, so a toggle sent twice lands wherever it started. `Grid` and `Hud` got
`set visible`, `CameraDirector` got `setRotate(on, {grab})`, and `Viewer` exposes
`setRotate`/`setGridVisible`/`setHudVisible` with the keyboard delegating to the same methods — one
behaviour per action rather than an agent path and a human path that drift.

**`hold`.** `viewFrom` forced `mode='user'` because for a human pressing `1` it genuinely is a
handoff. For an agent it is not, and the cost was invisible: a build directed to view 1 framed stage
1 and let stages 2..N drift out of frame, so the camera stopped following exactly when there was most
to follow. Under `hold` the mode stays `agent`, and since `tick()` re-derives the viewing direction
from the camera's own position each frame and corrects only distance and target, the chosen angle is
*preserved and refit* as the build grows. `engageAgent()` now keeps a deliberately-set view name and
discards only `free`, so the HUD stops reporting an unattended camera while it is holding a chosen
view.

`controls.js` and the HUD hint stopped hardcoding `1-6` and derive it from `VIEW_COUNT`, so a seventh
view is one edit to the shared table rather than three that must agree. Carries I-13.

## Files changed

| File | Change |
|---|---|
| `apps/web/src/net/WsClient.js` | `onViewer`, fired after the diff |
| `apps/web/src/viewer/Viewer.js` | `applyViewerOps` + three setters; toggles delegate |
| `apps/web/src/viewer/CameraDirector.js` | `setRotate(on, {grab})`, `viewFrom(n, {hold})`, `engageAgent` keeps a preset name |
| `apps/web/src/viewer/Grid.js` | `set visible` |
| `apps/web/src/viewer/Hud.js` | `get`/`set visible`; hint derives from `VIEW_COUNT` |
| `apps/web/src/viewer/controls.js` | Preset keys derived from `VIEW_COUNT` |
| `apps/web/src/main.js` | `onViewer` wired; `applyLocal` collects `viewerOps`; five driver methods |
| `tests/viewer-ops.test.js` | New — 16 cases |

## Verification

`npm test` → 10 files, 130 tests passed (16 new). `npm run build` clean. Live against the running ws
server: the contract publishes all five ops, a mixed batch relays both viewer ops alongside the box,
and `view 99` is refused with `n must be an integer 1..6`. See I-13's Verification for what the
`hold` test actually proves and what remains unobserved in a browser.
