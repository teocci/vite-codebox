# Progress

**Current version:** 0.6.0
**Active phase:** P-10 and P-11 — a five-phase plan to make builds land at true 1:1 scale and give
the model primitives that sculpt. P-7 (F-1, F-2), P-8 (I-7), P-9 (I-8) and P-12 (I-5, I-6) are `done`
and unreleased; R2 closes with P-11 and ships all of them together. P-10 and P-11 are independent and
can run in parallel. 420 tests: 74 vitest, 112 Go unit, 24 Go e2e, 210 pytest (codeblox-builder, +1
skipped) — plus 54 pytest for the `dev-phase` skill family, which is chore-track tooling and is
counted separately.

> Counting note: the v0.4.0 entry records "136 tests: 44 vitest + 92 Go", understated even then. The
> v0.5.0 entry's "297 tests: … 27 Go e2e" was also wrong in one term — the e2e suite has 24 test
> functions and had 24 at that commit, so the v0.5.0 total should read 294 (59 + 107 + 24 + 104).
> Counts here are **top-level `func Test…`**, which is the method that reproduces the v0.5.0 unit
> figure of 107; counting subtests instead gives a much larger number. The v0.5.0 line is left as
> published rather than rewritten after the fact.

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
| 6 | Split `App` along its two domains | done |
| 7 | Close the two silent holes under the scale gate | done |
| 8 | Native ellipsoid and tube ops | done |
| 9 | The scale gate — declared subject dimensions, checked before send | done |
| 10 | SKILL.md: the authoring rule, the shape vocabulary, and the real part cost | planned |
| 11 | Make large world extents usable | planned |
| 12 | A build is a thing, to the skill and to the viewer (I-5, I-6) — retroactive, see `docs/PLAN.md` note 3 | done |

## Next action

**P-10 (I-9) and P-11 (I-10) are both unblocked and independent** — P-10 needs P-8 and P-9, P-11
needs P-9, and all are `done`. They can run in parallel, in separate sessions. R2 closes with P-11
and ships P-7, P-8, P-9, P-11 and P-12 together as one minor.

Two unscheduled fixes surfaced while verifying P-9, neither with an item yet: `world.fetch`'s
`--refresh` is not a flag `codeblox info` accepts, so a refresh is a usage error and preflight can
report a stale cached contract; and the running ws server is stale, publishing 8 ops without P-8's
`ellipsoid` and `tube` even though both are committed.

Longer-standing, and the only thread that changes what the product can do:

**WSS/TLS**, outstanding from Phase 2. The server runs plain `ws`, and the CLI
refuses to send a token over `ws://` to a non-loopback host — so remote use is blocked loudly rather
than silently, but it is blocked. This is the gate on running the server anywhere but localhost.

Operator note: `install_codeblox.py` has only ever been run with `--dry-run`. Writing to the User
PATH is the one irreversible-ish step in the skill and is left to be triggered deliberately with
`npm run install:cli`; everything works today through the resolver's repo-checkout rung.

> P-9 (done, unreleased): The scale gate (I-8). Every man-made build in `builds/` had landed at
> 15-26% of true size — the Tesla is 1.16 m against a real 4.97 m, the Golden Gate 22.4 m against
> 2737 m — and nothing could have noticed, because a block is 2 cm and no value existed anywhere for a
> check to compare against. A plan now declares `subject.mm`, and `build.py` measures the expanded
> plan's own AABB against it **before the first block is sent**, which is the only useful moment:
> `remove` takes an id, not a region, so there is no partial undo of a wrongly-sized build. The
> per-axis **ratio triple** is what makes the failure actionable, because it separates two cases whose
> remedies are opposite — a uniform miss is arithmetic and the new `dims.py fit` repairs it, while a
> proportion error is a geometry mistake and rescaling it would produce a correctly-sized wrong shape
> that then passes this very gate, so that envelope names the outlier axis and refuses to offer the
> rescale. Tolerance is 10% per axis with a one-block floor, which is not slack: `to_blocks` rounds to
> nearest, so a subject can be half a block out at each end through no fault of the plan. An oversized
> subject is reported on its own terms, naming the `world.extent` to raise rather than a smaller build
> — on the Golden Gate that is ≥1368.5, which is where P-11's `extent 1400` comes from. `subject` is
> **optional but validated**: no pre-existing plan becomes invalid, but a malformed one is refused
> because it would silently disable the gate it was written to enable. The new `dims.py` converts real
> dimensions to blocks (with spec-sheet L/W/H order as a flag, since transposing those fails quietly),
> rescales by moving **both corners** and deriving the size from them — rounding `at` and `size`
> independently opens a one-block seam at every joint — and expands shape calls first, because
> `segments`, `steps` and `thickness` are not lengths. The metre is now visible everywhere the block
> was: derived once in `world.digest`, stated by `doctor.py` on the rung that already held the
> contract, and reported per stage as it lands. The inherited draft's `factor` was a harmonic mean
> written as a chained `and` and scaled a too-big build *further up*; that was the first failing test.
> Live-verified end to end — declared Model S refused at exit 5, fitted, then built, 37 parts in 5
> stages, 4.96 m in the world — and that live run caught a fixed-width metre column printing
> `3.26 m620ms`. Detail: `docs/improvements/I-8.md`, `docs/phases/phase-9.md`.

> P-8 (done, unreleased): Two new part ops, `ellipsoid` and `tube` (I-7). The model had been using
> `sphere` for car wheels, bear paws and human hands — `builds/bear.json` is 17 spheres out of 17
> parts — and that is the correct choice from a wrong menu: `World._compose` composes every instance
> with `IDENTITY_QUAT`, so nothing is ever rotated and `cylinder` is y-axis only, making a car wheel
> (a cylinder about x) unbuildable; `sphere.r` is a scalar, so a squashed sphere — what a paw or a
> hood actually is — was equally unavailable. Both additions exploit capability the renderer already
> had. `ellipsoid` returns `kind: 'sphere'` because the instance matrix already applies a fully
> non-uniform scale, so it reuses the existing geometry *and* its `InstancedMesh` — no new draw call,
> eight lines of protocol, zero renderer. `tube` bakes its orientation into the vertex buffer
> (`rotateZ`/`rotateX` at construction) rather than rotating at runtime, so `_compose` stays identity
> and the permuted size **is** the world AABB — which is the point: no conservative-bounds arithmetic
> enters `protocol.js`, `World.js`, or `world.py`. Both are new **ops**, not new fields, and that is
> forced rather than stylistic: `contract.go:139-148` errors on any declared field absent from a
> command, so adding `axis` to `cylinder` would have broken all 23 cylinders already in `builds/`. A
> general rotation field was declined (for a box or ellipsoid a 90° turn is the same shape with a
> permuted size; arbitrary rotation ends the integer-block invariant in four places), and so was a
> native `wedge` — a suspension cable is a catenary, not a ramp, and at 253 blocks a stepped roofline
> has 8 cm risers, so fixing the scale removes most of what motivates one. Detail:
> `docs/improvements/I-7.md`.

> P-7 (done, unreleased): Two silent holes closed before the scale work could rest on them, both
> found while planning rather than by hitting them. **F-1**: the CLI's welcome frame carries the whole
> world snapshot and `transport` never called `SetReadLimit`, so `coder/websocket`'s 32 KiB default
> capped the world at ~330 parts — measured at 5349 bytes of envelope plus 79.6–86.8 bytes per part
> against the real builds. Past that, every command failed at the handshake including the `clear`
> that would have recovered it, while `codeblox info` kept serving a cached contract and reporting a
> healthy server. It had never fired because the largest existing build is 52 parts; at 1:1 a car is
> ~90 and a building ~200, so two builds cross it. **F-2**: `world.aabb()` fell through to `None` for
> any unrecognised op, and `None` is the module's signal for "occupies nothing", so `fill` passed the
> client-side bounds gate unchecked and would only be refused server-side mid-build — where `remove`
> takes an id, so there is no partial undo. The fix is the inverted default, not the missing case: an
> explicit `CONTROL_OPS` allowlist returns `None` and everything else must have a case or raise, so
> the two ops P-8 adds and the plan-extent measurement P-9 builds on the same function cannot
> silently escape. The raise is a new `AnchorError(WorldError)` caught *before* its parent, because
> an unmeasurable op is exit 5 (rejected here), not exit 4 (server unreachable). F-1's test was
> confirmed non-vacuous by reverting the one-line fix. Detail: `docs/fixes/F-1.md` ·
> `docs/fixes/F-2.md`.

> P-12 (done, unreleased): Placed here by date, not by id — the work landed at `8c99d21` between
> P-6 and P-7, outside the phase structure, and only got a row (P-12) afterwards so that it had some
> route to a version at all. **I-5** gave `codeblox-builder` a workflow where it had a pipeline: a
> plan is named stages, and every stage is expanded, bounds-checked and dry-run *before* the first
> block is sent. A plan either builds or nothing moves — a correctness property, not an ergonomic
> one, because `remove` takes an id rather than a region, so a bad material in the last stage of
> five used to surface after four had already landed, with no way back but `clear`. The staging
> also turned out to be choreography: `DropAnimator` never re-animates a settled part, so every
> submitted batch is exactly one animation beat, and a forty-part castle sent flat lands as one
> undifferentiated shower. A carve step was in the originating sketch and had to be removed —
> `applyBatch` resolves `remove` by id over scaled parts, so there is no boolean subtraction and
> openings are *composed*. An undo ledger was declined: it would be a second source of truth for
> world state in a project whose locked invariant is that the server is authoritative, and its
> competitor — `clear` plus a re-run of a pre-validated plan — is one command and deterministically
> identical. **I-6** is the other half, and the reported symptom was blunt: build the white house,
> inspect it, build the bridge, and the camera never moves. Two causes stacked on a third. Only
> `world.onClear` ever handed the camera back, and neither plan had a `clear` stage; even in agent
> mode `_worldBounds()` fitted *all* parts, so two builds 500 blocks apart became two specks. The
> one underneath is that the viewer had no concept of a build — it saw a stream of parts and
> therefore *could not* know which were the new thing, and no timing heuristic recovers that, since
> `build.py` paces a 100-part stage at 2.1 s, so the gap *within* one build is unbounded and any
> threshold eventually splits a build in two. The fix is a domain event rather than a threshold: a
> field-less `build_begin` control op the server relays and `build.py` sends ahead of stage 1, after
> which the viewer groups the build's ids and frames that sphere. **Zero Go changes**, which is the
> schema-driven design paying out — `contract.Ops` is unmarshalled from the published payload, so
> the CLI picked the op up the moment the server restarted, and it refuses an *unpublished* op
> client-side with exit 5, which is what makes the marker safe against an older server. Not covered
> by any automated check: the camera motion in a real browser after a human has dragged the canvas.
> Detail: `docs/phases/phase-12.md` · `docs/improvements/I-5.md` · `docs/improvements/I-6.md`.

> P-6 (v0.6.0): Split `App`, which had grown to 9 public methods across two unrelated concerns —
> credential lifecycle and world building — sharing only the injected substrate. Now a `base` struct
> embedded in `authApp` and `buildApp`, with `base` and everything connection-shaped moved to a new
> `app.go`; `Deps.app` became `newBase` plus two constructors, and `buildApp` is handed no
> `PromptSecret`, which is where the boundary is actually enforced. The honest measure: it narrows the
> **method set**, not the data — `Env`, `Store`, `Stdout`, `Dial` and even `Stdin` are used by both
> halves (`Stdin` carries the token for `auth login` and the batch for `exec`), so `PromptSecret` is
> the only genuinely domain-owned field. What changed is that a build verb can no longer reach a
> credential prompt, enforced by the compiler rather than by which file a function was typed into.
> `connect`/`session` stayed shared on purpose: I-2 consolidated them because `auth status` had been
> duplicating those steps and returning an unclassified exit 1, so a per-half copy would have reopened
> that — `base.connect`'s doc comment now names I-2 so the reason travels with the code. `App.Stderr`
> was dropped, having been populated at construction and read by nothing. Behaviour-preserving, and
> the evidence is that no test assertion was edited — only the two constructors the tests call. Four
> new reflection guards in `app_test.go` pin the boundary, since the compiler is equally happy if
> someone re-merges the halves. `-race` was not run: it needs cgo and this toolchain has no C
> compiler. Detail: `docs/phases/phase-6.md` · `docs/improvements/improvement-4.md`.

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
