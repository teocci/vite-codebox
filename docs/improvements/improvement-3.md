# I-3 — End-to-end test harness

- **Item ID:** I-3
- **Version:** 0.5.0
- **Date:** 2026-07-26
- **Tests:** 13 e2e (12 passing, 1 skipped pending P-5), tagged out of the default suite
- **Status:** ✅ DONE (released in v0.5.0).

## Objective

Give the CLI a suite that drives the **built binary as a subprocess**, so the properties a caller
actually depends on are covered: which stream carries what, and the exit code. The package-adjacent
unit tests call Go functions and never spawn a process, so neither is reachable from them — and both
are exactly what P-5's Python wrappers will branch on.

## Why a separate directory, when Go tests are normally package-adjacent

Go's test tooling is directory-scoped: `*_test.go` files compile *into* the package in their own
directory, which is why every unit test here lives beside its package and uses the internal flavour
(`package command`) to reach unexported identifiers. There is no way to put those elsewhere.

Integration tests are the documented exception — they test no package, they test a binary. They get
their own directory and a build tag so `go test ./...` stays fast and hermetic, and so a suite that
wants a running server never blocks the default run.

## What was built

`clients/codeblox/tests/`, package `tests`, every test file behind `//go:build integration`:

| File | Role |
|---|---|
| `doc.go` | package doc and how to run it. **Untagged on purpose** — with a tag on every file the directory would have no Go files to compile and `go build ./...` would fail on it |
| `e2e_main_test.go` | `TestMain` builds the binary from current source; `run` executes it hermetically; `requireFailure` and `requireServer` helpers |
| `cli_test.go` | 9 tests needing no server — the I-1 regressions asserted at the binary boundary |
| `world_test.go` | 4 tests driving a live world, skipped when the server is down |
| `testdata/bridge.ndjson` | a five-command batch fixture |

Run it with `npm run test:e2e`, or `go test -tags=integration ./tests/`. `npm run test:cli` runs the
default unit suite.

Three properties the harness guarantees:

- **It cannot pass against a stale artifact.** `TestMain` runs `go build` into a temp dir rather than
  reusing `bin/codeblox`.
- **It cannot touch the operator's credentials.** Every invocation runs with `USERPROFILE`/`HOME`
  pointed at a per-test temp dir and `CODEBLOX_AUTH_BACKEND=file`, so the real `~/.codeblox` is never
  read or written and the OS keyring is never involved.
- **It degrades instead of failing.** Tests needing a world probe `127.0.0.1:7799` and skip with an
  actionable message when nothing is listening, so the suite is useful without `npm start`.

`requireFailure` asserts the shape a wrapper detects: non-zero exit, reason on stderr, and **nothing
on stdout** — a failure that writes to stdout is what let `exec batch.json --json` be mistaken for a
result. That last assertion is the one this suite adds beyond I-1's unit table.

## The harness caught a real bug on its first run

`testdata/bridge.ndjson` was written with piers at `y: -8`, below the floor. The server rejected two
commands as out of bounds. Bounds are server-side only by design (P-4: the published schema types
fields, it does not describe geometry), so nothing client-side could have caught it — which is
precisely the class of error this suite exists to surface, and the reason P-5's `shapes.py` needs the
anchor-drift guard below.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/tests/doc.go` | new — untagged package doc |
| `clients/codeblox/tests/e2e_main_test.go` | new — build, hermetic runner, assertion and skip helpers |
| `clients/codeblox/tests/cli_test.go` | new — no-server e2e |
| `clients/codeblox/tests/world_test.go` | new — server-gated e2e |
| `clients/codeblox/tests/testdata/bridge.ndjson` | new — batch fixture |
| `package.json` | added `test:cli` and `test:e2e` |

## Verification

- `go build ./...` clean and `go test ./...` unchanged — the new directory reports `[no test files]`,
  confirming the tag excludes it from the default run.
- `go vet -tags=integration ./tests/` clean.
- `go test -tags=integration ./tests/` — 12 pass, 1 skip, against a live server.

## Two deliberate hooks left open

- **`exitFailure`** is a single constant standing in for today's catch-all `os.Exit(1)`. When **I-2**
  introduces the taxonomy (2 usage · 3 auth · 4 network · 5 client contract · 6 server), the
  assertions tighten to specific codes and that constant is the only place to change.
- **`TestAnchorConventionMatchesTheServer`** is skipped pending **P-5**. It is the drift guard for
  `shapes.py`, which must encode the box-corner / sphere-centre rule locally because that rule is the
  one piece of geometry `world_info` does not publish.
