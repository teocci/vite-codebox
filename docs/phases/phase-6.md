# Phase 6 — Split `App` along its two domains

- **Phase ID:** 6
- **Version:** 0.6.0
- **Date:** 2026-07-26
- **Tests:** 298
- **Status:** ✅ DONE (298 tests; live-verified).

## Objective

Carries I-4. `App` has 9 public methods spanning two unrelated concerns — credential lifecycle (`Login`/`Logout`/`List`/`Status`) and world building (`Exec`/`RunOne`/`RunBatch`/`Info`/`Materials`) — sharing only `Env`, the credential store, the three streams, `Dial`, and `PromptSecret`. That is the god-object ceiling (~7-10 public methods, conventions and the no-spaghetti rule). The seam is already drawn by the file split `auth.go` / `build.go`; the refactor makes it a type boundary, so the compiler enforces what is currently only a convention.

Behaviour-preserving: no verb, flag, exit code, stream assignment, or JSON shape changes. I-3's e2e suite is the guard — it drives the built binary and asserts stream separation and exit codes, so any regression there fails the build rather than reaching the `codeblox-builder` wrappers.

Scope note: `connect`/`session` currently live in `build.go` but serve **both** domains — I-2 consolidated them there precisely because `App.Status` had been duplicating those steps and returning an unclassified exit 1. They belong on the shared base, not in either half. Full rationale and the open questions: `docs/improvements/improvement-4.md`.

## What was built

One `App` became a shared `base` embedded in `authApp` and `buildApp`, with `base` and everything
connection-shaped moved into a new `app.go`. `Deps.app` became `Deps.newBase` plus two thin
constructors, and `buildApp` is handed no `PromptSecret` — the enforcement sits at the one place the
objects are made.

The honest measure of the win: it narrows the **method set**, not the data. `Env`, `Store`, `Stdout`,
`Dial` and even `Stdin` are used by both halves (`Stdin` carries the token for `auth login` and the
batch for `exec`), so `PromptSecret` is the only genuinely domain-owned field. What changed is that a
build verb can no longer reach a credential prompt and an auth verb can no longer reach a command
batch, enforced by the compiler instead of by which file a function was typed into.

`connect`/`session` stayed shared, deliberately. I-2 consolidated them because `auth status` had been
duplicating those steps and returning an unclassified exit 1; splitting them per-half would have
reopened that. The doc comment on `base.connect` now names I-2 so the reason travels with the code.

`App.Stderr` was dropped — set in three places, read in none, because failures are rendered by
`Dispatch`'s caller.

Full rationale, the resolved open questions, and the four boundary guards: `docs/improvements/improvement-4.md`.

## Files changed

| File | Change |
|---|---|
| `internal/command/app.go` | **New.** Package doc, `Session`, `base`, and the shared `connect` / `session` / `dial` / `emitJSON`. |
| `internal/command/app_test.go` | **New.** Four guards pinning the type boundary. |
| `internal/command/auth.go` | `App` → `authApp`; shared helpers moved out. |
| `internal/command/build.go` | `App` → `buildApp`; connection plumbing moved out. |
| `internal/command/dispatch.go` | `Deps.app` → `newBase` + `authApp` + `buildApp`. |
| `internal/command/dispatch_build.go` | Routes through `d.buildApp`. |
| `internal/command/auth_test.go`, `build_test.go` | Constructors updated; `buildApp` helper renamed `newBuildApp`. |

## Verification

Behaviour-preserving, so the evidence is that every pre-existing suite passes with no assertion
edited — only the two test constructors changed.

| Suite | Before | After |
|---|---|---|
| vitest | 59 passed | 59 passed |
| Go unit | 107 test funcs, green | 111 test funcs, green |
| Go e2e (`-tags=integration`) | 24 test funcs, green | 24 test funcs, green |
| skill pytest | 104 passed, 1 skipped | 104 passed, 1 skipped |

131 → 135 test funcs module-wide: the four new guards, none lost. `gofmt -l` clean, `go vet ./...`
clean, unit and e2e both green under `-shuffle=on`. I-3's e2e suite is what makes the
behaviour-preserving claim checkable — it builds from current source and asserts exit codes and
stream separation, the two properties the `codeblox-builder` wrappers branch on.

**`-race` was not run:** it requires cgo, and this toolchain has no C compiler. The change adds no
concurrency, but the check did not execute and is not being reported as passing.
