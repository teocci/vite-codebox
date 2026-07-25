# Progress

**Current version:** 0.4.0
**Active phase:** none — v0.4.0 released (P-4, the schema-driven build verbs; 136 tests: 44 vitest
+ 92 Go). P-5, the last phase of the plan, is unblocked and ready to start.

Detail files: `docs/phases/` · `docs/improvements/` · `docs/fixes/`. Active plan: `docs/PLAN.md`.

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Engine + viewer, driven locally | done |
| 2 | Authoritative WS server + transport security | done |
| 3 | codeblox CLI foundation — config, credentials, transport | done |
| 4 | Schema-driven build verbs — info, exec, and the ergonomic forms | done |
| 5 | codeblox-builder agent skill | planned |

## Next action

Implement **P-5** — `skills/codeblox-builder/SKILL.md`, the agent skill: discovery through
`codeblox info` rather than hard-coded tables, the op vocabulary, batching, the coordinate
convention, worked examples (box-plus-sphere and a bridge), and guardrails (stay in bounds, use only
material names `world_info` returns, prefer few large parts). Ready now; it closes the plan.

Open follow-up from Phase 2, not yet scheduled: the server still runs plain `ws`. WSS/TLS —
native or behind a reverse proxy — is required before the CLI connects to a VPS over the network.
P-3 already refuses to send the token over plain `ws://` to a remote host, so that gap now blocks
remote use loudly rather than silently.

> Phase 4 (done): Made the CLI schema-driven and gave it the build verbs. `internal/contract` models
> the published `world_info` — config, palette, and each op's field-type map — so the binary compiles
> in no op list and no material names; both arrive from the server and cache at
> `~/.codeblox/world_info.json`. `ValidateCommand` walks the *published* field spec (`int3`,
> `int3+`, `int+`, `id`, `material`) and defers unrecognised types to the server, so a future op
> needs no client release. `transport.SendBatch` submits a `commands` frame and reads *past* the
> broadcast `diff` to the sender's `ack` — the server broadcasts before acking, so taking the first
> frame would misreport every build. A `Session` interface now sits between the verbs and the socket,
> making every verb testable without a network. `ParseBatch` accepts a JSON array, a single object,
> or NDJSON; `RunBatch` validates the whole batch before sending anything, and `--dry-run` stops
> after validation. `materials` serves from the cache without dialling. Ergonomic
> `box`/`sphere`/`cylinder`/`remove`/`clear` route through the same validated path. Verified live: a
> five-command NDJSON bridge built (`addedIds:[1,2,3,4]`), a bad material was refused before any
> send, and an out-of-bounds box was refused by the server with a non-zero exit. Bounds are
> deliberately server-side only — the published schema describes types, not the box-corner /
> sphere-centre geometry, so checking them client-side would duplicate `shared/protocol.js`.

> Phase 3 (done): Built `clients/codeblox/`, the operator-PC Go binary. `internal/config` injects
> the host environment (home, cwd, getenv) so every path is testable and nothing resolves relative
> to the executable; it declares every filename and `CODEBLOX_*` variable, and resolves the endpoint
> `--endpoint` → env → `~/.codeblox/config.json` → `ws://127.0.0.1:7799`. `internal/creds` keeps the
> token in the OS keyring via `go-keyring`, falling back automatically to a `0600`
> `~/.codeblox/auth.json` when no keyring answers; the stored credential beats `$CODEBLOX_TOKEN`,
> and `Mask` blanks tokens under 12 characters entirely instead of leaking most of a short secret.
> `internal/transport` performs the `hello`/`welcome` handshake, keeps `contract` and `parts` as raw
> JSON so the CLI stays schema-driven, and translates a 4001 close into an actionable
> "unauthorized". `CheckTransportSecurity` runs before the dial and refuses plain `ws://` to a
> non-loopback host without `--insecure`. `internal/command` ships `auth login|logout|list|status`
> with `--json` on the read verbs. Verified live against a server with `authRequired: true`: the
> wrong token is rejected, the right one connects and returns the contract. Deviated from the plan
> on three points, each recorded in `docs/phases/phase-3.md`: the env prefix is `CODEBLOX_` (the
> plan's `CODEBOX_` contradicts `server/auth.js`), profiles stay deferred, and `login` does not
> verify — `status` is the live check.

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
