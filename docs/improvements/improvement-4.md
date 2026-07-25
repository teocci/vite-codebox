# I-4 — Split `App` along its two domains

- **Item ID:** I-4
- **Version:** 0.6.0
- **Date:** 2026-07-26
- **Tests:** 298 (4 added: the boundary guards in `app_test.go`)
- **Status:** ✅ DONE (released in v0.6.0).
- **Related work:** P-6 carries it. Follows I-1 (per-verb flag surfaces) and I-2 (the exit taxonomy),
  both of which reshaped this package; deliberately deferred past P-5 so a refactor of shipped code
  would not tangle with new work.

## Objective

`App` is the CLI's injected context and has grown to **9 public methods spanning two unrelated
concerns**:

| Domain | Methods | Declared in |
|---|---|---|
| Credential lifecycle | `Login`, `Logout`, `List`, `Status` | `auth.go` |
| World building | `Exec`, `RunOne`, `RunBatch`, `Info`, `Materials` | `build.go` |

That is the god-object ceiling — ~7–10 public methods, no unrelated concerns in one unit. The two
halves share only the injected substrate: `Env`, `Store`, the three streams, `Dial`, and
`PromptSecret`.

The seam is already drawn by the file split. This makes it a **type** boundary rather than a filename
one, so the compiler enforces what is currently only a convention.

## Constraint: behaviour-preserving

No verb, flag, exit code, stream assignment, or JSON shape changes. The e2e suite from I-3 is the
guard: it drives the built binary and asserts stream separation and exit codes, so a regression in
any of those fails the build rather than reaching the `codeblox-builder` wrappers.

## Approach

One `App` became a shared `base` embedded in two domain types:

```go
type base struct {                  // injected substrate, shared
    Env    config.Env
    Store  creds.Backend
    Stdin  io.Reader
    Stdout io.Writer
    Dial   func(context.Context, transport.Dialer) (Session, error)
}

type authApp  struct{ base; PromptSecret func(string) (string, error) }
type buildApp struct{ base }
```

`base` and everything connection-shaped — `Session`, `dialOptions`, `connection`, `connect`,
`session`, `dial`, `emitJSON` — moved to a new `app.go`, which also carries the package doc. That
file is the answer to the question the refactor kept raising: *where does the shared part live?*
Leaving `connect` in `build.go` while `auth status` called it was the arrangement that made the
sharing invisible in the first place.

### What the split does and does not buy

It narrows the **method set**, not the data. Checking real usage first: `Env`, `Store`, `Stdout`, and
`Dial` are used by both halves, and so is `Stdin` — it carries the token for `auth login` (`readToken`)
and the batch for `exec` (`ParseBatch`). **`PromptSecret` is the only genuinely domain-owned field.**
So the win is that a build verb can no longer reach a credential prompt and an auth verb can no
longer reach a command batch, enforced by the compiler rather than by which file a function was
typed into.

### `connect` stays shared — the constraint that shaped everything

`connect` and `session` serve both domains. I-2 found `auth status` returning an unclassified exit 1
precisely because `App.Status` had been repeating those four steps instead of sharing them; the fix
routed both through one `App.connect`. Giving each half its own copy would reopen that bug, so both
live on `base`. The doc comment there now says so, naming I-2, so the next person to look at the
duplication has the reason in front of them.

### The two open questions, resolved

- **Where `Deps.app` lands.** Split into `Deps.newBase` plus two thin constructors, `Deps.authApp`
  and `Deps.buildApp`. `buildApp` gets no `PromptSecret` — that is the enforcement, at the one place
  the objects are made.
- **Whether build verbs still open the credential store.** Yes, uniformly. `connect` resolves the
  token from it, so every verb that dials needs it; `materials` served from cache is the lone
  exception, and special-casing it would add a branch in exchange for nothing observable.

### Dead field removed

`App.Stderr` was set in three places and read in none — failures are rendered by `Dispatch`'s caller
(`RenderFailure` in `main.go`), so no verb ever wrote to it. It is not on `base`.

## Files changed

| File | Change |
|---|---|
| `internal/command/app.go` | **New.** Package doc, `Session`, `base`, `dialOptions`, `connection`, and the shared `connect` / `session` / `dial` / `emitJSON`. |
| `internal/command/app_test.go` | **New.** Four guards that pin the boundary this item created. |
| `internal/command/auth.go` | `App` → `authApp` (embeds `base`, owns `PromptSecret`); `dial` / `emitJSON` moved out; `encoding/json` and `transport` imports dropped. |
| `internal/command/build.go` | `App` → `buildApp`; `dialOptions`, `connection`, `connect`, `session` moved out; `creds` import dropped. |
| `internal/command/dispatch.go` | `Deps.app` → `Deps.newBase` + `Deps.authApp` + `Deps.buildApp`; `Stderr` no longer copied onto the app. |
| `internal/command/dispatch_build.go` | Routes through `d.buildApp`. |
| `internal/command/auth_test.go` | Helper returns `*authApp`. |
| `internal/command/build_test.go` | Helper `buildApp` renamed `newBuildApp` — the bare name is the type now — and returns `*buildApp`. |

## Verification

Behaviour-preserving, so the evidence is that the pre-existing suites still pass unchanged — no test
assertions were edited, only the two constructors they call.

| Suite | Before | After |
|---|---|---|
| vitest | 59 passed | 59 passed |
| Go unit (`go test ./...`) | 107 test funcs, green | 111 test funcs, green |
| Go e2e (`-tags=integration`) | 24 test funcs, green | 24 test funcs, green |
| skill pytest | 104 passed, 1 skipped | 104 passed, 1 skipped |

Test-function count went 131 → 135 across the module: exactly the four guards added, none lost.
`gofmt -l` clean, `go vet ./...` clean, and the unit and e2e suites both pass under `-shuffle=on`.

The e2e suite is what makes "behaviour-preserving" a claim rather than a hope: it builds the binary
from current source in `TestMain` and asserts exit codes and stream separation, which is what the
`codeblox-builder` wrappers branch on. It passed unchanged.

**Not run: `-race`.** `go test -race` requires cgo, and this toolchain has `CGO_ENABLED=0` with no C
compiler available. The refactor introduces no goroutines or shared mutable state, so there is
nothing new for it to find, but the check was not executed and should not be reported as passing.

### The four guards

`app_test.go` tests the boundary itself, since that is the whole deliverable and the compiler would
happily accept it being undone:

- `TestEachDomainTypeExposesItsOwnVerbs` — the positive half; without it the negative test would pass
  vacuously against two empty types.
- `TestNeitherDomainTypeExposesTheOthersVerbs` — re-merging the types fails here.
- `TestBuildAppCannotPromptForASecret` — `FieldByName` walks embedded structs, so it fails whether
  `PromptSecret` is added to `buildApp` directly or promoted onto `base`.
- `TestNeitherDomainTypeCarriesADeadStream` — records why `base` has no `Stderr`.
