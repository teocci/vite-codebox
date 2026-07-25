# Progress

**Current version:** 0.5.0
**Active phase:** none — **v0.5.0 released**, closing the plan. P-5 (the codeblox-builder skill)
shipped with its three prerequisite items: I-1 (per-verb flag validation), I-3 (end-to-end test
harness), and I-2 (machine-readable failure contract). 297 tests: 59 vitest, 107 Go unit, 27 Go e2e,
104 pytest (skill).

> Counting note: the v0.4.0 entry records "136 tests: 44 vitest + 92 Go". Those figures were
> understated even then — a run at that commit gives more — so treat 297 as the first count taken
> from an actual run rather than as the size of one release's delta.

Test commands: `npm test` (vitest) · `npm run test:cli` (Go unit) · `npm run test:e2e` (Go
integration, `//go:build integration`, skips the world tests when no server is listening).

Detail files: `docs/phases/` · `docs/improvements/` · `docs/fixes/`. Active plan: `docs/PLAN.md`.

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Engine + viewer, driven locally | done |
| 2 | Authoritative WS server + transport security | done |
| 3 | codeblox CLI foundation — config, credentials, transport | done |
| 4 | Schema-driven build verbs — info, exec, and the ergonomic forms | done |
| 5 | codeblox-builder agent skill (carries I-1, I-3, I-2) | done |

## Next action

The plan is closed; nothing is scheduled. Two threads remain, neither blocking:

- **I-4** — split `App` along its two domains (credential lifecycle vs world building; 9 public
  methods, at the god-object ceiling). Hygiene, not a defect. Deliberately deferred past P-5 so a
  refactor of shipped code would not tangle with new work.
- **WSS/TLS**, still outstanding from Phase 2. The server runs plain `ws`, and the CLI refuses to
  send a token over `ws://` to a non-loopback host — so remote use is blocked loudly rather than
  silently, but it is blocked. This is the gate on running the server anywhere but localhost.

Operator note: `install_codeblox.py` has only ever been run with `--dry-run`. Writing to the User
PATH is the one irreversible-ish step in the skill and is left to be triggered deliberately with
`npm run install:cli`; everything works today through the resolver's repo-checkout rung.

> P-5 (v0.5.0): Built `.claude/skills/codeblox-builder/` — the agent skill, script-first.
> Six scripts, each justified by one probabilistic failure it removes: `resolve_codeblox.py` (no path
> hard-coded anywhere — `--bin`, `$CODEBLOX_BIN`, `$PATH`, then a dev checkout, each proved with
> `codeblox version`, and a named-but-missing binary is a hard error rather than a fall-through),
> `install_codeblox.py`, `doctor.py`, `world.py`, `shapes.py`, `submit.py`. SKILL.md keeps only what
> needs judgment: design, proportion, material choice, and "prefer few large parts". The anchoring
> rule — `box` at its minimum corner, `sphere` and `cylinder` at their centre, with a cylinder's
> height centred too — lives in exactly one place, because it is the one piece of geometry
> `world_info` does not publish and so the one at risk of drifting; a behavioural e2e guard now pins
> it against a live server. Three bugs surfaced while building: `npm run build:cli` was producing an
> **extensionless** binary on Windows that `where.exe` cannot find, with a stale `codeblox.exe`
> beside it that the resolver then picked; `auth status` returned an unclassified exit 1 because I-2
> classified the build path while `App.Status` repeated the same four steps (both now share one
> `App.connect`); and `--at -20,0,-3` failed to parse, since argparse reads a leading `-` as an
> option — fatal for a world that is half negative. Verified by building a real scene: a 40-block
> bridge with piers and railings, a marble arch, and a solid staircase, 25 parts, ids 1–25. The
> installer has only been run with `--dry-run`. Detail: `docs/phases/phase-5.md`.

> I-2 (v0.5.0): Gave failure a machine-readable contract. Every failure exited `1`, so the
> skill's wrappers could not tell *not authenticated* (→ re-auth) from *unreachable* (→ retry) from
> *material not in the palette* (→ re-plan): three behaviours behind one code, separable only by
> regex-matching English. `internal/command/exit.go` defines 2 usage · 3 auth · 4 network · 5
> client-side contract rejection (nothing sent) · 6 server rejection, carried by a `Failure` wrapper
> with three properties that make it safe at any depth — `fail(nil)` is nil, the **innermost**
> classification wins (a dial that fails because the token was refused stays auth, not network), and
> it survives `%w` via `errors.As`. `transport.ErrUnauthorized` is exported so the 4001 close is
> matchable without message text. With `--json`, failures now emit
> `{"ok":false,"code":...,"exit":N,"detail":...}` on stderr, so one parser covers both paths; the
> exit code is inside the envelope too, for a caller that captured only the streams. `--dry-run`
> honours `--json` at last, as a distinct shape (`validated`, `sent: 0`) because "nothing was sent"
> and "sent, 0 landed" must not be confusable. `WantsJSON` scans argv rather than reading the parsed
> flag — a usage error happens before parsing succeeds, and those are the failures a script hits
> most. Bare `codeblox` now writes usage to stderr and exits 2; `help` stays a success on stdout,
> because a request is not a mistake. **Two breaking changes for callers**, both in the changelog: a
> failure no longer always exits 1, and bare invocation no longer exits 0. Detail:
> `docs/improvements/improvement-2.md`.

> I-3 (v0.5.0): Added `clients/codeblox/tests/`, the end-to-end suite. Go's test tooling is
> directory-scoped — `*_test.go` compiles into the package in its own directory — so unit tests must
> stay package-adjacent and cannot spawn a process. That left the two properties a wrapper actually
> branches on uncovered: which stream carries what, and the exit code. The suite drives the built
> binary behind `//go:build integration`, so `go test ./...` is untouched. `TestMain` builds from
> current source, so it can never pass against a stale `bin/codeblox`; every invocation runs with
> `USERPROFILE`/`HOME` at a temp dir and `CODEBLOX_AUTH_BACKEND=file`, so the operator's real
> credentials are never read, written, or prompted for; and the four world tests skip with an
> actionable message when nothing listens on 7799. `requireFailure` adds the assertion the unit table
> could not make — a failure must write **nothing** to stdout, which is what let `exec batch.json
> --json` pass for a result. It caught a bug on its first run: the bridge fixture put piers at
> negative Y and the server rejected them as out of bounds, which nothing client-side could have
> caught, since bounds are deliberately server-side only. Two hooks left open: `exitFailure` is the
> single constant I-2 tightens into a taxonomy, and `TestAnchorConventionMatchesTheServer` is skipped
> pending P-5's `shapes.py`. Detail: `docs/improvements/improvement-3.md`.

> I-1 (v0.5.0): Gave every verb its own flag surface. One shared `FlagSet` had been handing
> all 14 flags to all 8 build verbs, so a foreign flag parsed cleanly and was ignored — `clear --r 5
> --id 9` reported success having done nothing. Worse, no verb checked `NArg()`, and stdlib `flag`
> stops at the first non-flag token: `exec batch.json --json` dropped `--json`, printed prose to
> stdout, and exited 0, which would have made P-5's `submit.py` parse an English sentence as JSON and
> crash — showing the agent a wrapper traceback instead of a CLI error. `auth logout`/`auth list`
> accepted a stray argument outright. `internal/command/flags.go` now holds `flagSurface`; `buildVerbs`
> and `authSubs` map each verb to its registrar, and that lookup also rejects unknown verbs. Argv
> validation and command construction moved ahead of `d.app()`, so nothing opens the keyring to
> discover that `--mat` is missing. Errors name the verb, the offending token, and the valid set on
> one line, printed once instead of three times. `Deps.PromptSecret` is wired through at last. A CLI
> framework was evaluated and declined: three agents scored six options on independent rubrics and
> stdlib was the argmax on all three — the defect was one constructor serving eight verbs, not a
> missing library. Re-open from kong (not cobra) if the verb count passes 20, a second nesting level
> appears, completion is wanted, or verbs must be generated from `world_info` at runtime. Detail and
> the full rationale: `docs/improvements/improvement-1.md`.

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
