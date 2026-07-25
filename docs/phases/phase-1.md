# Phase 1 — Engine + viewer, driven locally

- **Phase ID:** 1
- **Version:** 0.2.0
- **Date:** 2026-07-25
- **Tests:** 44 (suite total at release; live-verified in the browser console)
- **Status:** ✅ DONE (44 tests; live-verified).

> Retrospective. Phase 1 was built before this tracking structure existed and is recorded here as
> part of the `v0.2.0` baseline release.

## Objective

Stand up the block engine and the Three.js viewer with no server in the loop, so the geometry,
material, and camera behaviour could be proven before any transport existed. The driver had to
mimic the diff shape a server would later emit, so Phase 2 could swap it out without touching the
engine.

## What was built

**`shared/` — the dependency-free source of truth.** `config.js` plus `config.values.js`
(compiled from `config.yaml` by `scripts/gen-config.mjs`) make `BLOCK_SIZE` a single dial in
metres per block; a literal metre anywhere else is a bug. World extent is measured in metres and
is deliberately decoupled from block size, so a small block does not shrink the world.
`materials.js` and `families.js` define the palette and its four render families (opaque, glass,
metal, emissive). `protocol.js` holds the op vocabulary with `validate` and `expand`;
`examples.js` carries the worked batches.

**`src/engine/` — O(1) part management.** `InstancedLayer` keeps one `InstancedMesh` per
(geometry × render family) and adds/removes in constant time via swap-remove backed by a
bidirectional id↔slot index. `World` orchestrates the layers and applies diffs. `DropAnimator`
ticks only in-flight ids, which is what guarantees settled parts never re-animate.

**`src/viewer/` — the human-facing surface.** `Viewer` owns the renderer and loop;
`CameraDirector` gives the agent the camera and yields it the moment the human touches the mouse;
`Grid` draws 1m cells regardless of block size; `Hud` reports parts, extent, materials used, and
camera owner.

**`src/main.js`** exposed `window.codeblox` as the local driver — `exec` / `remove` / `clear`
running the same shared `expand` the server would later run.

## Files changed

| File | Change |
|---|---|
| `config.yaml`, `scripts/gen-config.mjs`, `shared/config.js`, `shared/config.values.js` | One-dial config compiled from YAML; no `.env` |
| `shared/materials.js`, `shared/families.js` | Palette with explicit render-family tags |
| `shared/protocol.js`, `shared/examples.js` | Op vocabulary, `validate`/`expand`, worked batches |
| `src/engine/InstancedLayer.js` | O(1) add/remove via swap-remove + id↔slot index |
| `src/engine/World.js`, `src/engine/geometry.js`, `src/engine/materials.js` | Layer orchestration, box/sphere/cylinder geometry, material construction |
| `src/engine/DropAnimator.js` | Drop animation over in-flight ids only |
| `src/viewer/Viewer.js`, `CameraDirector.js`, `Grid.js`, `Hud.js`, `controls.js` | Renderer, agent-owned camera, 1m grid, HUD |
| `src/main.js` | `window.codeblox` local driver |
| `src/styles/*`, `index.html`, `vite.config.js` | Page shell and styling |

## Verification

- `npm run dev`, then in the console:
  `codeblox.exec([{op:'box',at:[0,0,0],size:[10,20,10],mat:'oak'},{op:'sphere',at:[5,20,5],r:5,mat:'glass'}])`
  → one draw call per active (geometry × family) layer, confirmed via `renderer.info`.
- `codeblox.remove(<box id>)` → the sphere does not re-animate.
- `codeblox.clear()` → the framer re-fits; dragging mid-build makes the framer yield.
- Unit suites: `tests/shared.test.js`, `tests/instanced-layer.test.js`, `tests/world.test.js`,
  `tests/examples.test.js`.

## Notes / follow-ups

The tracking structure (`docs/`, `CHANGELOG.md`, the `dev-phase-*` bindings) did not exist while
this phase was worked; it was introduced with the `v0.2.0` baseline release. Phase ids therefore
start allocating at `P-3`.
