# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-25

Baseline release. Establishes codeblox end to end for a local operator: a block engine and viewer
driven by an authoritative WebSocket server, with the agent as the primary operator and the human
as reviewer. Phases 1 and 2 were built before the phase-tracking structure existed and are
recorded here as one baseline.

### Added

- P-1: `shared/` — a dependency-free source of truth for configuration, materials, render
  families, and the command protocol. `BLOCK_SIZE` is a single dial compiled from `config.yaml`
  into `shared/config.values.js`; no literal metre appears anywhere else.
- P-1: `InstancedLayer` — O(1) part add and remove via `InstancedMesh` swap-remove backed by a
  bidirectional id↔slot index, one instanced mesh per (geometry × render family).
- P-1: `DropAnimator` — drop-in animation that ticks only in-flight ids, so settled geometry is
  never touched again.
- P-1: Three.js viewer — `CameraDirector` (the agent owns the camera until the human touches the
  mouse), a 1m-cell floor grid decoupled from block size, and a HUD.
- P-1: `window.codeblox` local driver exposing `exec` / `remove` / `clear`, mimicking the diff
  shape the server would later emit.
- P-2: Authoritative Node WebSocket server — bearer-token handshake with `commander` / `viewer`
  roles, an in-memory `WorldStore`, server-side validation and expansion of command batches,
  server-assigned part ids, and diff broadcast to all subscribers.
- P-2: Full-world snapshot on connect, applied as settled geometry so a reconnect replays nothing.
- P-2: `WsClient` — drops in for the local driver behind the same diff shape, leaving the engine
  untouched, with a local-apply fallback when the server is unreachable.
- P-2: `npm start` — runs the viewer (:5173) and the server (:7799) together.

[Unreleased]: https://github.com/teocci/vite-codebox/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/teocci/vite-codebox/releases/tag/v0.2.0
