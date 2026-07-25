# Progress

**Current version:** 0.2.0
**Active phase:** none — v0.2.0 released (baseline: Phases 1–2, engine + viewer + authoritative
server, 44 vitest tests). Next work is the Go CLI + agent skill.

Detail files: `docs/phases/` · `docs/improvements/` · `docs/fixes/`. Active plan: `docs/PLAN.md`.

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Engine + viewer, driven locally | done |
| 2 | Authoritative WS server + transport security | done |

## Next action

Scaffold and implement the Phase 3 work (Go CLI `clients/codeblox/` + `skills/codeblox-builder/`),
split into context-sized phases per conventions §2.

> Phase 2 (done): Made the server authoritative. `server/createServer.js` accepts `ws`
> connections behind a bearer-token handshake (`server/auth.js`, token generated to
> `.codeblox/token` at runtime), assigns a `commander`/`viewer` role, and keeps the world in
> `server/WorldStore.js`. Clients send command batches; the server validates and expands them
> through the shared protocol (`server/commands.js`), assigns ids, and broadcasts diffs — a
> connecting client first receives a full snapshot applied as settled geometry, so nothing
> re-animates on reconnect. `src/net/WsClient.js` swaps in for the Phase 1 local driver behind the
> same diff shape, leaving the engine untouched; `src/main.js` falls back to applying commands
> locally when the server is unreachable. Port 7799 — 8787 hits a Windows EACCES excluded range.
> `npm start` runs viewer (:5173) and server (:7799) together via `concurrently`.

> Phase 1 (done): Built the block engine and viewer with no server in the loop. `shared/` is the
> dependency-free source of truth — `config.js` + `config.values.js` (compiled from `config.yaml`
> by `scripts/gen-config.mjs`, so `BLOCK_SIZE` is the one metre dial), `materials.js` /
> `families.js` (render families: opaque, glass, metal, emissive), `protocol.js` (op vocabulary,
> validate + expand), `examples.js`. `src/engine/InstancedLayer.js` gives O(1) add/remove via
> swap-remove with a bidirectional id↔slot index, one `InstancedMesh` per (geometry × family);
> `World.js` orchestrates, `DropAnimator.js` ticks only in-flight ids so settled parts never
> re-animate. `src/viewer/` has the Three.js `Viewer`, a `CameraDirector` the agent owns until the
> human touches the mouse, a 1m-cell `Grid` decoupled from block size, and the `Hud`.
> `src/main.js` exposed `window.codeblox` as the local driver, mimicking the diff shape the server
> would later produce.
