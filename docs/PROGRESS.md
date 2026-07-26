# Progress

**Current version:** 0.8.0
**Active phase:** none — R3 shipped as `v0.8.0`: P-13 (F-3) and P-14 (I-11), two independent
housekeeping phases that stopped two things lying. `world.py` no longer offers a refresh the CLI
never accepted, and the shipped skill's `.codex/`/`.agents/` mirrors now fail a test when they drift
instead of going quietly stale. 488 tests: 95 vitest, 112 Go unit, 24 Go e2e, 257 pytest
(codeblox-builder, +1 skipped) — plus 54 pytest for the `dev-phase` skill family, which is
chore-track tooling and is counted separately.

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
| 10 | SKILL.md: the authoring rule, the shape vocabulary, and the real part cost | done |
| 11 | Make large world extents usable | done |
| 12 | A build is a thing, to the skill and to the viewer (I-5, I-6) — retroactive, see `docs/PLAN.md` note 3 | done |
| 13 | Stop world.py asking for a cache the CLI does not have | done |
| 14 | Make the skill mirrors provable rather than remembered | done |

## Next action

**No active plan.** R3 shipped as `v0.8.0` and `docs/PLAN.md` is back to its stub — the next plan
starts with `dev-phase-start`.

One thing R3 surfaced and deliberately did not act on: **`.agents/rules/` is orphaned.** Twelve
tracked markdown files with no source anywhere in this repo — `.claude/` tracks only `settings.json`
and `skills/` — and their names (`01-pre-implementation.md`, `02-javascript-style.md`, …) no longer
match the global rule set they appear to have been copied from. `.codex/` carries no `rules/` at all,
so the two hosts were never mirroring the same set. They cannot be synced from anything here, and
they are stale by construction rather than by drift. Most likely they should be deleted; that was not
I-11's call to make, since they look like personal content. Wants an explicit decision.

Not scheduled, and deliberately not a phase: **`builds/white-house.json` still predates the scale
gate** — no `subject` declaration, so it has never been measured against the real building.
`tesla-model-s.json` (305 parts) and `golden-gate-bridge.json` (386 parts, rebuilt during P-11 at
2737 m) both declare and pass. `builds/` is gitignored, so rebuilding it changes no tracked file and
cannot be a release-track item; it is work to do, not work to track. The bridge needs
`world.extent: 1400`; the shipped default is 32.

Longer-standing, and the only thread that changes what the product can do:

**WSS/TLS**, outstanding from Phase 2. The server runs plain `ws`, and the CLI
refuses to send a token over `ws://` to a non-loopback host — so remote use is blocked loudly rather
than silently, but it is blocked. This is the gate on running the server anywhere but localhost.

Operator note: `install_codeblox.py` has only ever been run with `--dry-run`. Writing to the User
PATH is the one irreversible-ish step in the skill and is left to be triggered deliberately with
`npm run install:cli`; everything works today through the resolver's repo-checkout rung.

> Phase 14 (done): Made the skill mirrors provable rather than remembered, and closed R3 (I-11).
> `codeblox-builder` ships to three agent hosts from one authored source, and the `.codex/` and
> `.agents/` copies had gone stale after P-7, P-9 and P-10 — three times, silently, because a stale
> mirror is indistinguishable from a fresh one until someone runs it. P-13 had just made it four. The
> mechanism is two pieces and only one of them is the point: `scripts/sync-skills.mjs` copies the 18
> source files and removes what the source no longer has, and `tests/skill-mirrors.test.js` fails when
> a mirror differs. A sync script alone would have been a fourth manual step to forget; the test is
> what converts "remember to sync" into "the suite goes red". Mapping the source first narrowed the
> work twice: only `codeblox-builder` is mirrored (the `dev-phase-*` skills are chore-track tooling for
> this repo's own workflow, never shipped to a host), and frontmatter is byte-identical across all
> three copies, so the mirrors need no per-host adaptation and a plain copy plus equality check is
> sufficient — had any host needed to differ, this approach would have been wrong. The mirrors stay
> **committed** rather than generated-and-gitignored: ignoring them makes drift structurally
> impossible, which is the stronger guarantee, but a mirror exists so another host can read the skill
> straight from a checkout and a generated one is absent exactly when wanted. Both were three files
> short (`dims.py`, `test_dims.py`, `test_doctor.py`) and ten behind. Verified as a mechanism, not an
> assertion: the test was watched failing before the sync existed, then again on a deliberately
> drifted line in `.codex/…/world.py` — naming that one path — then green after `1 written`; and
> `pytest` against the `.codex` mirror passes 257, so the copies are usable rather than merely equal.
> A `--check` mode was written and removed before finalizing, since `npm test` already asks that
> question and a second path would be one more thing to keep honest. Left alone deliberately:
> `.agents/rules/` is twelve tracked files with **no source in this repo** — orphaned rather than
> drifted, and deleting what looks like personal content is not this item's call. 95 vitest, 488
> total. Detail: `docs/improvements/I-11.md`.

> Phase 13 (done, unreleased): Stopped `world.py` asking for a cache the CLI does not have (F-3).
> `world.fetch(refresh=True)` sent `--refresh` to `codeblox info`, which rejects it — since I-1 made
> an unknown flag a hard error rather than a silent no-op, every refresh was exit 2. The flag could
> not simply be registered on the verb: `Info` calls `a.session(...)` directly and never reaches
> `contractFromCache`, so `info` dials the server on every call and only *writes* the contract file.
> `materials` is its only reader, which is why `materials` is the only verb the flag belongs on. Making
> `--refresh` meaningful on `info` would have meant making `info` cache-first — and `info` dialling is
> exactly what makes it `doctor.py`'s liveness check, so the "fix" would have broken preflight to
> satisfy a flag with no caller. Deleted instead, at all three levels: parameter, argv, CLI flag. No
> production caller was touched — `build.py`, `dims.py`, `doctor.py` and `submit.py` all call
> `fetch(binary)` bare. The load-bearing half is the docstring, which had asserted both the cache read
> and the refresh, and whose wrong model had already cost a misdiagnosis: P-9's genuinely stale server
> was recorded as a stale cache and answered by hand-deleting a cache file, when the fix was a
> restart. It now states that if the contract looks out of date the *server* is stale. The deleted
> test is worth noting on its own — `test_refresh_is_passed_through` asserted `'--refresh' in argv`,
> which only ever verified that the mock received what the code sent, never that the CLI would accept
> it, so it stayed green for the whole life of the defect; its replacement asserts argv by equality,
> which fails the moment an unaccepted argument is added. 257 pytest (+1 skipped), 484 total. This
> also makes the `.codex/`/`.agents/` copies one change staler — P-14 is what closes that, and its
> drift test would have caught this on landing. Detail: `docs/fixes/F-3.md`.

> Phase 11 (done): Made a large `world.extent` actually usable, and closed R2 (I-10). P-9's scale
> gate answers an oversized subject by naming the extent that would hold it at 1:1 — but the viewer
> carried three literals tuned for the 64 m world that shipped, so that advice was false past about a
> kilometre. The far plane was the defect and it was arithmetic, not opinion: at a fixed 5000 m, a
> 2737 m span sits at a fit distance of ~4224 m with its far corner at ~5597 m, and clipped. The fix
> was not a larger constant. `maxOrbit` (twelve extents) is handed to OrbitControls as `maxDistance`,
> and the far plane is that cap plus the buildable box's half-diagonal — so nothing can be further
> from the camera than a distance the camera is forbidden to reach, which turns "the world never clips
> away" from generosity into a guarantee. The near plane stopped being a trade rather than being
> rebalanced: a near that tracks far at a fixed ratio needs clamping at both ends, and every clamp is
> a scale at which it is wrong, so `logarithmicDepthBuffer` carries the precision and near is simply
> one block everywhere. The grid was a legibility problem, not a geometry one — what matters is cell
> *count* — so `gridStepFor` climbs a 1-2-5 ladder holding the floor near 64 divisions, keeping the
> number round (a derived 43.75 m cell is legible to nobody, 50 m is), and `gridStep: auto` is the new
> default. All four are **pure functions of the extent**, not getters reading config, which is why the
> suite exercises seven extents from 1 m to 5000 m and passes identically at 32 and at 1400 — and why
> the tests assert invariants (far exceeds cap plus half-diagonal; grid holds 25–70 divisions across
> four decades) instead of restating the formulas. A pre-existing test was coupled the same way the
> viewer was, asserting a literal 4000-block box out of bounds — true only at `extent: 32`; it now
> derives from `WORLD.boundBlocks`. `extent` itself stays **32**: raising it is the point of the
> phase, but shipping the maximum as the default would put a 5 m car on a 50 m grid inside a 2.8 km
> floor, trading the case everyone builds for one nobody builds by default. Live-verified by
> rebuilding `builds/golden-gate-bridge.json` at true 1:1 in an `extent: 1400` world — 2737 m end to
> end, 1280 m main span, 227 m towers, 143 m sag, 386 parts; no clipping at either deck end, 50 m grid
> at 56 divisions, no z-fighting across 256 cable segments. The first attempt at that subject put the
> towers at ±1280 m instead of ±640 m — 1280 m is the *main span*, not the half-length — which is a
> reminder that a render-envelope probe still has to be the right shape to be read. One behaviour
> change: the reviewer can no longer dolly past twelve extents (384 m at the default), where before
> the far plane allowed 5000 m at any extent. Detail: `docs/improvements/I-10.md`.

> P-10 (done, unreleased): The skill stops teaching the error, and gets the shapes it was telling the
> model to hand-build (I-9). Two halves. First, `SKILL.md` did not merely fail to warn that a block is
> 2 cm — it *demonstrated* the opposite: a castle `size [40,14,40]` is 80 cm, and the proportion advice
> recommended a 16 cm bridge deck. A worked example outranks a caveat, and after P-9 the cost of
> leaving them changed in kind, because the documentation now led the model into a refusal the
> documentation could not explain. Both are replaced by a 6 m pavilion that declares `subject.mm`, and
> every command in the file was executed before being written down — which is how the `pane` example
> was caught emitting 116 parts for one windshield. The metre value stays out of the prose: the file's
> own rule is that runtime values come from the server, so it points at `blocksPerMetre` and
> `dims.py to-blocks`. Second, the cost model was false and measurably so: `addPart` keys layers as
> `kind:family` on the *render family* with per-instance colour, so forty boxes of forty different
> opaque materials are **one** draw call, and with five geometry kinds and four families the whole
> world is bounded at twenty draw calls at any part count. What costs is an instance slot plus
> `frustumCulled = false`, so every instance is submitted each frame whether on screen or not; and
> after F-1's `SetReadLimit(-1)` there is no protocol ceiling either. So the advice inverts — part
> count is cheap, and the curved and raked forms this phase adds *need* many parts. Five generators
> close the gap between what the skill told the model to do and what it gave it to do it with:
> `wheel` (a `tube` with a hub standing proud, since flush it is invisible), `taper` (spires and
> hulls, heights distributed by integer division so no slab is zero-tall and consecutive slabs share a
> face exactly), `dome` (an `ellipsoid` of twice the rise, half buried, refusing a base that cannot
> clear it), `window` (a wall composed around an opening, omitting zero-sized pieces so a door and a
> shopfront are the same generator) and `pane`. `pane` is the load-bearing one and is forced by the
> renderer: `_compose` uses `IDENTITY_QUAT`, so nothing is ever rotated and a raked surface must be a
> staircase of thin slabs — the rebuilt Tesla spends 178 of its 305 parts stepping exactly that by
> hand. Its frame is *inset* into the glazing rather than added around it, so framing cannot grow a
> build past its declared subject and trip P-9's gate over a cosmetic choice; and it caps both ends,
> which was only discovered by looking at the render — framing the long rails alone left bare glass at
> each end and read as two loose strips. Detail: `docs/improvements/I-9.md`, `docs/phases/phase-10.md`.

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
