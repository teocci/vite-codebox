# Phase 11 — Make large world extents usable

- **Phase ID:** 11
- **Version:** 0.7.0
- **Date:** 2026-07-27
- **Tests:** 483
- **Status:** ✅ DONE (483 tests; live-verified).

## Objective

The scale gate now tells the operator which extent would fit a subject at 1:1. Three hardcoded viewer literals make that advice a lie past about 1.2 km.

## What was built

I-10, the last row of R2 — the four extent-coupled values in the viewer become derivations of
`world.extent`: the camera's near plane, far plane and opening position, plus the floor grid's cell
size. Each is a pure function in `packages/shared/config.js`, which is why the suite can exercise
seven extents from 1 m to 5000 m and pass identically at `extent: 32` and `extent: 1400`.

The far plane was the actual defect. It is now derived from an explicit orbit cap handed to
OrbitControls as `maxDistance`, plus the buildable box's half-diagonal — so nothing can be further
away than a distance the camera is forbidden to reach. A logarithmic depth buffer removes the
near/far trade entirely, letting the near plane be one block at every scale. The grid step climbs a
1-2-5 ladder that holds the floor near 64 cells, and returns exactly 1 m at `extent: 32`, so the
shipped world is visually unchanged.

`extent` stays at 32. Raising it is the point of the phase; shipping the maximum as the default
would trade the common case for a case nobody builds by default.

The phase also closes R2 and releases P-7, P-8, P-9, P-10 and P-12 with it.

## Files changed

| File | Change |
|---|---|
| `packages/shared/config.js` | `gridStepFor`, `cameraPlanesFor`, `cameraStartFor`, `resolveGridStep`; five new `WORLD` getters |
| `apps/web/src/viewer/Viewer.js` | Planes and opening position derived; `logarithmicDepthBuffer: true` |
| `apps/web/src/viewer/CameraDirector.js` | `controls.maxDistance = WORLD.maxOrbit` |
| `scripts/gen-config.mjs` | `gridStep` defaults to `'auto'` |
| `config.yaml` | `gridStep: auto`; extent documented as a working knob |
| `tests/shared.test.js` | 17 new tests; one pre-existing extent-coupled assertion rederived |

## Verification

483 tests: 91 vitest, 112 Go unit, 24 Go e2e, 256 pytest (+1 skipped). Green at both `extent: 32`
and `extent: 1400`. Production `vite build` clean.

Live-verified by rebuilding `builds/golden-gate-bridge.json` at true 1:1 (2737 m, 386 parts) in a
`extent: 1400` world: no clipping at either deck end, 50 m grid legible at 56 divisions, no
z-fighting across 256 cable segments.

## Notes / follow-ups

- **`builds/golden-gate-bridge.json` was rebuilt at true 1:1** during live testing — 1280 m main span
  with the towers correctly bracketing it, 143 m cable sag, 386 parts. It had predated the scale gate
  and carried no `subject` declaration. `builds/` is untracked, so the plan is reproducible from the
  generator rather than from the repo; the file needs `extent: 1400` to build.
- **The reviewer can no longer dolly past 12 extents** (384 m at the default). Previously the far
  plane allowed 5000 m at any extent. This is the mechanism that makes the far plane provable, and at
  384 m a 64 m world is already a speck — but it is a behaviour change.
- Carried over, neither caused nor fixed here: the `codeblox-builder` skill is still unmirrored to
  `.codex/` and `.agents/`, and `world.fetch(refresh=True)` still sends a `--refresh` flag that
  `codeblox info` rejects, so a stale cached contract has to be deleted by hand.
- `builds/white-house.json` still predates the scale gate.
