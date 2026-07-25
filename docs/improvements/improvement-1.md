# I-1 — Per-verb flag validation

- **Item ID:** I-1
- **Version:** 0.5.0
- **Date:** 2026-07-25
- **Tests:** 97 Go (93 before; +4 table-driven suites)
- **Status:** ✅ DONE (released in v0.5.0).

## Objective

Make the CLI reject argv it does not understand. Every verb shared one `flag.FlagSet` carrying all
14 flags, so a flag that belonged to another verb parsed cleanly and was silently ignored. The CLI's
consumer is a script driven by an agent: a human notices a no-op, an agent receives a success-shaped
result and proceeds on a false premise. This is a prerequisite for P-5, whose Python wrappers parse
this binary's output.

## What was built

`internal/command/flags.go` introduces `flagSurface`, one verb's argv contract — its own `FlagSet`
plus `parse`, which rejects both unknown flags and positional arguments. `buildFlags` and `authFlags`
embed it, and each verb registers only the flags it actually reads: `buildVerbs` and `authSubs` map a
verb name to its registrar, so the map lookup is also what rejects an unknown verb.

Flag fields became values rather than pointers. A verb that never registers a flag simply leaves the
field at its zero value, which removes the nil-pointer hazard that a per-verb split would otherwise
introduce.

Errors are written for a machine reader: `clear: flag provided but not defined: -r; valid flags:
--backend, --config, --dry-run, --endpoint, --insecure, --json` — verb, offending token, and the
valid set on one line, the shape `internal/contract` already uses for unknown ops and materials. The
`FlagSet`'s own output is discarded (`io.Discard`); left attached it printed the bare message plus a
dump of every default, and the caller then printed the error again — the same failure three times.

Validation was moved ahead of every side effect. `dispatchBuild` now parses argv **and** builds the
verb's command before `d.app()` opens the credential store, and `dispatchAuth` resolves the
subcommand first, so `auth renew --backend file` no longer probes the OS keyring for a subcommand
that does not exist, and `box` with no `--mat` fails without touching it.

`Deps.PromptSecret` is now wired through to `App`. It was declared and read but never assigned, so
the fallback read the real `os.Stdin` — an interactive `auth login` test would have blocked on the
terminal.

### Three defects fixed, all confirmed against a built binary

| # | Before | After |
|---|---|---|
| a | `codeblox clear --r 5 --id 9` parsed clean, ignored everything | rejected, names `-r` and the valid set |
| b | `codeblox exec batch.json --json` **discarded `--json`** — stdlib `flag` halts at the first non-flag token and nothing checked `fs.NArg()` — printed prose to stdout and **exited 0** | rejected, names `"batch.json"` |
| c | `--dry-run` was registered on `info`/`materials`, whose option structs have no `DryRun` field | rejected |

The red-phase run showed (b) was broader than reported: *every* verb ignored a stray positional and
proceeded to real work, and **`auth logout batch.json` and `auth list batch.json` succeeded
outright**. `auth status --with-token` was accepted and ignored — (a) in the auth path.

## Decision recorded: no CLI framework

Three agents scored six options (stdlib-fixed, cobra, cobra+koanf, cobra+viper, kong, urfave/cli v3)
on independent rubrics — codebase fit, machine-consumer correctness, supply chain. **stdlib was the
argmax on all three** (91 / 89 / 94); no non-negative weighting selects another. The defect was one
constructor serving eight verbs, not a missing library.

Findings that decided it beyond the scores: cobra's `go.mod` declares `go 1.15`, which disables Go's
module graph pruning — 7 modules enter `go.sum` (including `blackfriday`, a markdown parser) for 2
linked — and it links `mousetrap` on Windows, which on Explorer-launch prints help then calls
`fmt.Scanln()` and **blocks**, on the platform this CLI targets, for a consumer that cannot answer.
viper and koanf were disqualified rather than outscored: they add multi-source config merging to a
`Config` struct with **one field**, and `CODEBLOX_TOKEN` shares the `CODEBLOX_` prefix with the
config vars, so a natural env provider would ingest the token into a tree that gets serialized —
inverting the invariant `config.go` states as *"Adding a credential field here is a bug."*

**Re-open the question — starting from kong, not cobra — when any of:** the verb count exceeds 20; a
second nesting level appears; a human operator asks for shell completion; or the ergonomic verbs must
be generated from `world_info` at runtime. That last case is the one where kong is also wrong (its
struct tags are compile-time). Carry forward: kong defaults to `os.Exit` on parse failure and must be
overridden with `kong.Exit()`, or it can terminate before piped stdin is drained.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/internal/command/flags.go` | new — `flagSurface`: per-verb `FlagSet`, unknown-flag and positional rejection, `validFlags` for error text |
| `clients/codeblox/internal/command/dispatch_build.go` | `buildVerbs` registrar map; value fields; validation and command construction moved ahead of `d.app()`; `shapeCommand` takes `*buildFlags` |
| `clients/codeblox/internal/command/dispatch.go` | `authFlags` + `authSubs`; subcommand resolved before the store opens; `Deps.PromptSecret` added and passed to `App` |
| `clients/codeblox/internal/command/dispatch_flags_test.go` | new — the contract table: every verb against every flag, positional rejection, and the `exec batch.json --json` regression |

`go.mod` is untouched: 3 direct and 3 indirect modules, unchanged. The argv surface is unchanged —
`--r` and `--h` still parse, so no wrapper needs rewriting.

## Verification

- `gofmt -l .` clean; `go vet ./...` clean; `go test ./...` green — **97 tests**.
- Table written first and confirmed failing against the old code before any production change.
- Against the built binary: (a), (b), (c), `auth status --with-token`, and `auth logout batch.json`
  all now exit 1 with a single actionable line; `auth renew --backend file` fails on the subcommand
  without opening a store; `sphere --at 0,0,0 --r 5 --mat oak --dry-run` and `cylinder --at 0,0,0
  --r 3 --h 8 --mat oak --dry-run` still parse, reaching the auth check.

## Deferred to I-2

The evaluators agreed a machine-readable *failure* contract matters more than the parser: every
failure still collapses to `os.Exit(1)`, `--json` covers only the success path, and bare `codeblox`
prints usage to stdout and exits 0.
