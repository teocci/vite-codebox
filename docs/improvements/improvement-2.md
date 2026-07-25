# I-2 — Machine-readable failure contract

- **Item ID:** I-2
- **Version:** 0.5.0
- **Date:** 2026-07-26
- **Tests:** 107 Go unit (+10), 24 Go e2e (+11), 59 vitest — 190 total
- **Status:** ✅ DONE (released in v0.5.0).

## Objective

Make failure legible to a script. Every failure exited `1`, so P-5's wrappers could not tell *not
authenticated* (→ re-authenticate) from *server unreachable* (→ retry with backoff) from *material
not in the palette* (→ re-plan). Three different behaviours behind one code, separable only by
regex-matching English that may be reworded at any time. `--json` covered only the success path, so
a wrapper needed two parsers; and a bare `codeblox` printed usage to **stdout** and exited **0**.

## What was built

`internal/command/exit.go` defines the taxonomy and the rendering:

| Code | Meaning | What a caller does |
|---|---|---|
| 0 | success | continue |
| 1 | unclassified | a gap in the table, not a category |
| 2 | usage | argv is wrong — fix the invocation |
| 3 | auth | no credential, or the server refused it — re-authenticate |
| 4 | network | unreachable, or refused as unsafe — retry, or fix the endpoint |
| 5 | contract | rejected here against the published schema; **nothing was sent** — re-plan |
| 6 | server | sent, and the server refused it (world bounds, for instance) |

`Failure` wraps an error with an exit code and a stable token. Three properties make it safe to use
at any depth:

- **`fail(nil)` is nil**, so call sites wrap unconditionally.
- **The innermost classification wins.** A dial that fails *because the token was refused* stays
  auth (3), not network (4) — the site closest to the cause knows best.
- **It survives `%w`.** `ExitCodeFor` uses `errors.As`, so adding context up the stack never loses
  the category.

`transport.ErrUnauthorized` is now an exported sentinel (the server's 4001 close), which is what lets
the dial site tell "your credential is wrong" from "the server is not there" without matching text.

**The `--json` envelope** goes to stderr whenever the caller asked for JSON:

```json
{"ok":false,"code":"not_authenticated","exit":3,"detail":"not authenticated — run `codeblox auth login`"}
```

The exit code is *inside* the envelope as well as on the process, so a caller that captured only the
streams still learns the category. `--dry-run` also emits JSON now (a distinct `dryRunReport` with
`validated` and `sent: 0` — "nothing was sent" and "sent, 0 landed" must not be confusable); it
printed prose regardless of `--json` before.

### One deliberate design call: how `--json` is detected

`WantsJSON` scans argv rather than reading the parsed flag. A **usage** error happens *before*
parsing succeeds, and usage errors are the ones a script hits most — insisting the flag was parsed
first would deny the envelope to exactly the failures that most need it. So the rule is "the caller
visibly asked for JSON", which also keeps `main.go` free of flag plumbing.

**Bare `codeblox`** now writes usage to stderr and exits 2. `help` is unchanged — it is a request,
not a mistake, so it stays a success on stdout. That distinction is the point: an empty argv is a bug
in the caller, and `help` is a result.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/internal/command/exit.go` | new — codes, `Failure`, `fail`, `ExitCodeFor`, `WantsJSON`, `RenderFailure` |
| `clients/codeblox/internal/command/exit_test.go` | new — 10 tests: every code, wrapping, innermost-wins, envelope shape, `WantsJSON` spellings |
| `clients/codeblox/main.go` | renders through `RenderFailure` and exits with `ExitCodeFor` |
| `clients/codeblox/internal/command/build.go` | classified auth / network / contract / server sites; `dryRunReport`; `--json` on the dry-run path |
| `clients/codeblox/internal/command/dispatch.go` | bare invocation → stderr + exit 2; usage classification; exit-code section in `help` |
| `clients/codeblox/internal/command/dispatch_build.go`, `flags.go` | argv errors classified as usage |
| `clients/codeblox/internal/transport/client.go` | `ErrUnauthorized` exported as a sentinel |
| `clients/codeblox/internal/command/dispatch_test.go` | `deps` returns stderr too — which stream carries a message is contract, not detail |
| `clients/codeblox/tests/*` | assertions tightened from "non-zero" to the specific code; `requireEnvelope` added |

`go.mod` is untouched.

## Verification

- `gofmt -l .` clean; `go vet ./...` and `go vet -tags=integration ./tests/` clean.
- **107 unit + 24 e2e + 59 vitest**, all green. 23 e2e pass, 1 skips (the P-5 anchor guard).
- Every code demonstrated against the built binary and a live server:

```
3 auth       {"ok":false,"code":"not_authenticated","exit":3,...}
4 network    {"ok":false,"code":"unreachable","exit":4,...}
5 contract   {"ok":false,"code":"contract_rejected","exit":5,...}   # nothing sent
6 server     {"ok":false,"code":"server_rejected","exit":6,"detail":"...out of world bounds"}
2 usage      codeblox: exec: unexpected argument "batch.json" — ...   # prose without --json
```

The 5-vs-6 split is the one worth checking by hand, and it holds: an unpublished material is caught
client-side (5, nothing sent) while an out-of-bounds box with a valid material reaches the server and
is refused there (6) — because bounds are deliberately server-side only.

## Note for I-3's successor tests

The e2e taxonomy constants are duplicated in `tests/e2e_main_test.go` rather than imported. That is
deliberate: the suite is black-box, and a test that imports the constants it checks cannot catch them
being renumbered.
