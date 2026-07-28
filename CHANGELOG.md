# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- I-12: Five viewer ops — `view`, `reframe`, `rotate`, `grid` and `hud` — in a third op category the
  server relays to every viewer and never stores. Five explicit ops rather than one grouped op with
  optional fields, because the Go client requires every declared field to be present. The `VIEWS`
  table moved to `packages/shared/views.js` so `protocol.js` can range-check `n` against
  `VIEW_COUNT`: while the table was module-scoped inside `CameraDirector.js`, `view 7` could only be
  a silent no-op, and to a blind agent a silent no-op is indistinguishable from success. Two
  behaviours are deliberate rather than incidental — a viewer op survives a `clear` in the same batch
  (a clear erases the world, but it does not make "look from view 1" moot), and viewer ops apply
  *after* the world diff regardless of batch position, so `[{view:1}, box, clear]` lands as
  `clear → box → view`. They ride the broadcast, not the ack, because the broadcast already includes
  the sender and the CLI's typed `Ack` drops fields it wasn't compiled for. Nothing moves on screen
  yet; that is P-16.

## [0.8.0] - 2026-07-27

the mirrors and the docs stop lying — a drift test for the shipped skill, and a refresh flag that never worked, removed

### Added

- I-11: `npm run sync:skills` mirrors the `codeblox-builder` skill from `.claude/` to `.codex/` and
  `.agents/`, and a test fails when they drift. The mirrors are copies of one authored source with
  identical frontmatter — no per-host adaptation — so every difference between them was drift, and
  they had gone stale after P-7, P-9 and P-10 because nothing failed when they did. The test is the
  part that matters; a sync script on its own would have been a fourth step to forget. Both mirrors
  were three files short (`dims.py` and two test modules) and ten files behind. They stay committed
  rather than generated-and-ignored, because a mirror exists so another agent host can read the skill
  straight from a checkout.

### Fixed

- F-3: `codeblox-builder`'s `world.py` no longer offers a `--refresh` that never worked. It forwarded
  the flag to `codeblox info`, which does not accept it, so any refresh was a usage error rather than
  a re-fetch. The flag could not simply be registered on the verb either: `info` dials the server on
  every call and only *writes* the contract cache — `materials` is its only reader, and is therefore
  the only verb the flag belongs on — so making `--refresh` meaningful would have meant making `info`
  cache-first, which is precisely what would stop it working as preflight's liveness check. The
  docstring had asserted both the cache read and the refresh, and that wrong model had a cost: a
  genuinely stale server was diagnosed as a stale cache, and answered by deleting a cache file when
  the fix was a restart. It now says so.

## [0.7.0] - 2026-07-27

builds land at true 1:1 — a scale gate that measures a plan against the real thing, native curved ops, five generators, and a viewer that scales with its world

### Added

- I-9: Five shape generators — `wheel`, `taper`, `dome`, `pane` and `window`. Two of them close gaps
  the skill previously described in prose and left as arithmetic: `window` composes a wall around an
  opening (sill, head, two jambs, optional glazing) because nothing in this engine subtracts, and
  `pane` builds raked glazing — a windshield, a backlight, a skylight — as a stack of thin slabs,
  because no part is ever rotated and a leaning surface cannot be a leaning box. The remaining three
  give the native ops something to be used by: `wheel` is a `tube` with a hub, `dome` an `ellipsoid`
  half-buried in what it sits on, `taper` the spire and hull shape `shell` cannot express.
- I-8: A build plan can declare the real size of its subject — `subject.mm`, in millimetres, in the
  protocol's own `x, y, z` — and the plan is measured against that declaration before the first block
  is sent. Every man-made build in the repo had landed at 15-26% of true size with nothing to notice:
  a block is 2 cm, and there was no value anywhere for a check to compare against. The per-axis ratio
  separates the two failures that look alike, because their remedies are opposite — a uniform miss is
  arithmetic and the new `dims.py fit` repairs it, while a mismatch in proportion is a geometry
  mistake and rescaling it would only produce a correctly-sized wrong shape. A subject larger than
  the world is reported on its own terms, naming the `world.extent` that would hold it. The field is
  optional, so no existing plan becomes invalid.
- I-8: `dims.py` converts real dimensions to blocks (`to-blocks`, with spec-sheet length/width/height
  order as a flag since transposing those fails quietly), rescales a plan to its own declaration
  (`fit`), and reports human-scale reference dimensions (`anchors`). A rescale moves both corners of
  every part and derives the size from them rather than scaling `at` and `size` independently, which
  would open a one-block seam at every joint.
- I-7: Two part ops, `ellipsoid` (`at` centre, `size` full extent) and `tube` (`at` centre, `r`, `h`,
  `axis`). The renderer could already draw both — the instance matrix carries a fully non-uniform
  scale, so a unit sphere becomes any axis-aligned ellipsoid — and `tube` gets its orientation from
  one of three baked geometries rather than a runtime rotation, so parts stay axis-aligned and every
  AABB stays exact. Additive: no existing op or field changed, and the CLI picks both up from the
  contract without a rebuild.
- I-6: A `build_begin` control op marks where one build ends and the next begins. The viewer had no
  concept of a build — it saw a stream of parts — so a second build arriving into a populated world
  looked like any other parts, and the camera stayed where it was. It now groups the ids that follow
  the marker and frames just those, instead of fitting every part in the world. Field-less and
  additive; the CLI picks it up from the published contract with no rebuild, and a server that does
  not publish it refuses the op client-side rather than failing mid-build.
- I-5: `codeblox-builder` builds from a declarative stage plan (`build.py`). Every stage is expanded
  and bounds-checked and the whole plan is dry-run *before* the first block is sent, so a bad
  material in the last stage of five is caught while nothing has landed — which matters because
  `remove` takes an id, so there is no partial undo. Stages then land one at a time with progress,
  paced off the real settle time, which is also what makes a build read as being built rather than
  arriving as one shower. `--from N`, `--only NAME` and `--no-focus` for iterating.

### Changed

- I-10: The viewer's camera derives its near plane, far plane and opening position from
  `world.extent` rather than carrying three literals tuned for a 64 m world. The far plane was a
  fixed 5000 m, which made the scale gate's own advice — "raise `extent` and this subject fits at
  1:1" — false past about a kilometre: a 2737 m span sits at a fit distance of ~4224 m with its far
  corner at ~5597 m, and clipped. Rather than pick a larger constant, the far plane is now derived
  from an explicit orbit cap, handed to the controls as `maxDistance`, plus the buildable box's
  half-diagonal — so nothing can be further from the camera than a distance the camera is not
  allowed to reach. A logarithmic depth buffer carries the precision across that range, which
  removes the near/far trade rather than rebalancing it: the near plane is simply one block at every
  extent. The reviewer can no longer dolly past twelve extents, which is the cap the guarantee rests
  on.
- I-10: `world.gridStep` accepts `auto` — now the default — and derives a round 1-2-5 cell that
  holds the floor grid near 64 divisions at any extent. Pinned at 1 m it drew 2800 divisions in a
  1400 m world and read as a solid grey sheet, and what matters for a reference grid is the cell
  count rather than the cell size. A 32 m world still gets exactly the 1 m cell it always had, and a
  pinned number still overrides.
- I-9: The `codeblox-builder` skill no longer teaches that a block is a metre by worked example. Its
  castle was 40 blocks across — 80 cm — and its proportion advice recommended a 16 cm bridge deck;
  both are replaced by an example that declares its real size and was built before being documented.
  Its cost guidance was also simply wrong: "forty boxes are 40x the cost of one" ignores that the
  renderer keeps one instanced mesh per geometry-kind-and-render-family and colours instances
  individually, so the entire world is at most twenty draw calls however many parts it holds. The
  guidance now says what actually costs — every instance is submitted each frame, visible or not —
  and stops steering away from the many-part forms curved and raked shapes need.
- I-8: The metre is now reported everywhere the block already was. `codeblox info`'s digest derives
  how many blocks span a metre, preflight states it on the rung that already had the contract in hand,
  and each stage of a build reports what it landed in metres as well as in parts. The conversion is
  derived from the published contract, never written down, so changing the block size changes all
  three with no edit.
- I-6: Build plans live in a gitignored `builds/` beside the work rather than in the repo root.
  `build.py` reads stdin and never opens a plan file, so the location stays a convention rather than
  a path baked into a script.
- I-5: The `codeblox-builder` skill documents a *workflow* rather than a pipeline, and its
  guardrails now state the two things that were only implicit: this engine cannot carve — openings
  are composed from parts around the gap, not subtracted — and there is no partial undo.

### Fixed

- F-1: The CLI no longer fails at the handshake once the world passes ~330 parts. The welcome frame
  carries the whole world snapshot and `transport` never lifted the websocket library's 32 KiB read
  limit, so past that size *every* command failed — including the `clear` that would have recovered
  the world, leaving a server restart as the only way out. Never hit before because the largest
  existing build is 52 parts.
- F-2: An out-of-bounds `fill` is now refused by the skill's client-side bounds gate instead of
  reaching the server mid-build, where there is no partial undo. `world.aabb()` had treated any op it
  did not recognise as occupying nothing; it now returns nothing only for an explicit control-op
  allowlist and raises otherwise, so no op added later can silently escape the gate.

## [0.6.0] - 2026-07-26

Split App along its two domains: a type per concern over a shared base

### Changed

- I-4: The CLI's `internal/command` package now has a type per domain — `authApp` for the credential
  lifecycle, `buildApp` for world building — over a shared `base` carrying the injected substrate.
  One `App` had been holding all nine verbs, so nothing but the file split kept a build verb from
  reaching a credential prompt. Internal only: no verb, flag, exit code, stream, or JSON shape
  changes, and `internal/` is not importable from outside the module.

### Removed

- I-4: `App.Stderr`, which was populated at construction and read by nothing — failures are rendered
  by `Dispatch`'s caller.

## [0.5.0] - 2026-07-26

codeblox-builder agent skill; per-verb flag validation and a machine-readable failure contract

### Added

- P-5: `codeblox-builder`, the agent skill — six tested scripts plus a SKILL.md that carries only
  what needs judgment. `resolve_codeblox.py` locates the binary (`--bin`, `$CODEBLOX_BIN`, `$PATH`,
  then a dev checkout) so no path is hard-coded anywhere; `install_codeblox.py` builds and registers
  it on the User environment; `doctor.py` preflights; `world.py` digests the published contract;
  `shapes.py` generates exact coordinates for shells, stairs, arches, and bridges; `submit.py` gates
  bounds, validates, sends, and reports `addedIds`.
- P-5: An anchor-drift guard in the e2e suite. `box` anchors at its minimum corner while `sphere` and
  `cylinder` anchor at their centre — the one piece of geometry `world_info` does not publish, and so
  the one at risk of silently diverging from the server.
- I-2: An exit-code taxonomy so a caller can branch on an integer instead of matching prose —
  `0` success, `2` usage, `3` auth, `4` network, `5` client-side contract rejection (nothing sent),
  `6` server rejection. Documented in `codeblox help`.
- I-2: A JSON failure envelope — `{"ok":false,"code":"...","exit":N,"detail":"..."}` on stderr
  whenever `--json` is given, so one parser covers both the success and failure paths.
- I-2: `--dry-run` honours `--json`, reporting `validated` and `sent: 0` as a distinct shape from a
  real submission.
- I-2: `transport.ErrUnauthorized`, so a refused token is distinguishable from an unreachable server
  without matching message text.
- I-3: End-to-end test suite at `clients/codeblox/tests/`, which drives the built binary as a
  subprocess and so covers what unit tests cannot — stdout/stderr separation and exit codes. Behind
  `//go:build integration`, so `go test ./...` is unchanged; run it with `npm run test:e2e`.
- I-3: `npm run test:cli` (unit) and `npm run test:e2e` (integration) as npm entry points.

### Fixed

- P-5: `npm run build:cli` produced an **extensionless** binary on Windows, which `where.exe` cannot
  find and CreateProcess will not launch, leaving a stale `codeblox.exe` beside it. Now builds with
  `go build -o bin/`, which names the artifact correctly on every platform.
- P-5: `codeblox auth status` returned an unclassified exit 1 for failures the build path already
  reported as auth or network. Both now share one classified `App.connect`.
- I-1: Every CLI verb shared one flag set carrying all 14 flags, so a flag belonging to another verb
  parsed cleanly and was silently ignored — `codeblox clear --r 5 --id 9` did nothing and reported
  success. Each verb now declares only the flags it reads and rejects the rest.
- I-1: `codeblox exec batch.json --json` silently discarded `--json`, printed prose to stdout, and
  exited 0, because stdlib `flag` stops at the first non-flag token and nothing checked `NArg()`. No
  verb takes a positional argument — batches arrive on stdin — and a stray one is now an error.
  `auth logout` and `auth list` previously accepted a stray argument and succeeded.
- I-1: `--dry-run` was accepted by `info` and `materials`, which have no dry-run behaviour.
- I-1: The credential store was opened before argv was validated, so `auth renew --backend file`
  probed the OS keyring for a subcommand that does not exist, and `box` with no `--mat` probed it
  before reporting the missing flag. Validation now precedes every side effect.
- I-1: `Deps.PromptSecret` was declared and read but never assigned, so an interactive `auth login`
  fell through to the real terminal instead of the injected reader.

### Changed

- I-1: Flag errors now name the verb, the offending token, and the valid set on one line — matching
  the shape `internal/contract` already uses — and are printed once rather than three times.
- **I-2 (breaking for callers reading exit codes):** a failing command no longer always exits `1`.
  Scripts that test for exactly `1` should test for non-zero, or branch on the new taxonomy.
- **I-2 (breaking):** bare `codeblox` with no arguments now writes usage to **stderr** and exits `2`,
  where it previously wrote to stdout and exited `0`. `codeblox help` is unchanged — it remains a
  success on stdout.

## [0.4.0] - 2026-07-25

Schema-driven build verbs: info, exec, and the ergonomic forms

### Added

- P-4: `codeblox info` — fetches the server's `world_info` contract, prints the world configuration,
  material count, and every published op with its field types, and caches it at
  `~/.codeblox/world_info.json`.
- P-4: `codeblox materials [--family F]` — lists the palette from the cache without contacting the
  server; `--refresh` forces a re-fetch.
- P-4: `codeblox exec` — reads a command batch from stdin as a JSON array, a single JSON object, or
  NDJSON. `--dry-run` validates and stops.
- P-4: Ergonomic single-command forms — `box`, `sphere`, `cylinder`, `remove`, and `clear` — routed
  through the same validated path as `exec`.
- P-4: Client-side batch validation against the *fetched* schema and palette. An unknown op, a bad
  material, a wrong-arity vector, or a non-positive size is rejected before anything is sent.
- P-4: `--json` on every build verb, reporting `ok`, `sent`, `addedIds`, `removed`, and `cleared`.

### Changed

- P-4: The CLI compiles in no op list and no palette; both arrive from the server, so a new material
  or op needs no client release.

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

[Unreleased]: https://github.com/teocci/vite-codebox/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/teocci/vite-codebox/releases/tag/v0.4.0
[0.3.0]: https://github.com/teocci/vite-codebox/releases/tag/v0.3.0
[0.2.0]: https://github.com/teocci/vite-codebox/releases/tag/v0.2.0
