# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-25

codeblox Go CLI: credentials, config, and authenticated transport

### Added

- P-3: `codeblox` Go CLI at `clients/codeblox/` — a self-contained operator binary that needs
  neither Node nor Python on the host.
- P-3: gh-style credential lifecycle — `auth login` (no-echo prompt, or `--with-token` from stdin),
  `auth logout`, `auth list`, and `auth status` with a live check against the server.
- P-3: OS keyring as the default token store, with an automatic fallback to a `0600` file store at
  `~/.codeblox/auth.json` on hosts with no keyring. Selectable via `--backend` or
  `CODEBLOX_AUTH_BACKEND`.
- P-3: Endpoint resolution — `--endpoint`, then `CODEBLOX_ENDPOINT`, then `~/.codeblox/config.json`,
  then `ws://127.0.0.1:7799`. The settings file holds non-secret values only; the token is never
  written to it and is masked everywhere it is printed.
- P-3: A transport guard that refuses to send the token over plain `ws://` to any non-loopback host
  unless `--insecure` is given, checked before the connection is opened.
- P-3: `--json` on `auth list` and `auth status` for compact machine-readable output, since an agent
  is the primary caller.

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
