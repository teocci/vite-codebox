# Phase 3 — codeblox CLI foundation — config, credentials, transport

- **Phase ID:** 3
- **Version:** 0.3.0
- **Date:** 2026-07-25
- **Tests:** 97
- **Status:** ✅ DONE (97 tests; live-verified).

## Objective

Stand up the Go module at `clients/codeblox/` with the gh-style credential and configuration
lifecycle, plus the WSS transport it will carry. The endpoint resolves from `~/.codeblox/` with
`--endpoint`/`CODEBLOX_ENDPOINT` overrides; the token lives in the OS keyring (go-keyring) with a
file-backend fallback for headless hosts, never in a config file, and is masked in all output.
Ships `auth login` (hidden prompt or `--with-token`/stdin), `auth logout`, `auth list`, and
`auth status` with a live check against the server.

## What was built

**`internal/config` — one base dir, one resolver.** `Env` injects the host's home dir, working dir,
and environment, so nothing resolves user data relative to the executable and every path is
testable. Every filename and `CODEBLOX_*` variable name in the CLI is declared here. The settings
file resolves `--config` → `$CODEBLOX_CONFIG` → a project-local `config.json` → `~/.codeblox/`; the
endpoint resolves `--endpoint` → `$CODEBLOX_ENDPOINT` → the settings file → `ws://127.0.0.1:7799`.
`Config` carries only non-secret fields; `ValidateEndpoint` rejects anything that is not `ws://` or
`wss://` at resolution time rather than deep inside the dialer.

**`internal/creds` — keyring first, file fallback.** A two-implementation `Backend` interface over
the OS keyring (`go-keyring`) and a 0600 JSON store at `~/.codeblox/auth.json`. `Open` picks by
`--backend`, then `$CODEBLOX_AUTH_BACKEND`, then probes the keyring and falls back to the file
store when no keyring daemon answers. `Resolve` implements the credential precedence: the stored
credential wins, `$CODEBLOX_TOKEN` is a fallback for automation only. `Mask` renders a token
printable — edges only, and tokens shorter than 12 characters lose their edges entirely rather than
leaking most of a short secret.

**`internal/transport` — the handshake, with a guard in front of it.** `Dialer.Connect` dials,
sends `{"type":"hello","token":…}`, and reads the server's `welcome`, keeping `contract` and
`parts` as raw JSON so the CLI stays schema-driven and compiles none of the server's vocabulary in.
A 4001 close is translated into an actionable "unauthorized" error. `CheckTransportSecurity` runs
**before** the dial and refuses to put a bearer token on a plain `ws://` link to any non-loopback
host unless `--insecure` is passed — loopback is exempt because that traffic never reaches a
network interface.

**`internal/command` — the verbs.** `App` holds injected dependencies (environment, store, I/O
streams, dialer) so every verb runs in tests with no keyring, no home directory, and no network.
`Dispatch` parses subcommands with the stdlib `flag` package. `auth login` reads the token from a
no-echo terminal prompt or from stdin with `--with-token`, stores it, and optionally records a
non-default endpoint in the settings file. `auth list` and `auth status` accept `--json` for compact
machine-readable output, since the agent — not a human — is the primary caller.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/go.mod`, `go.sum` | New Go module; `coder/websocket`, `zalando/go-keyring`, `x/term` |
| `clients/codeblox/main.go` | Entry point; builds the host `Env` and delegates to `Dispatch` |
| `clients/codeblox/internal/config/config.go` | Base dir, settings file, endpoint precedence, name constants |
| `clients/codeblox/internal/creds/store.go` | `Backend` interface, keyring + 0600 file backends, `Resolve`, `Mask` |
| `clients/codeblox/internal/transport/client.go` | `Dialer.Connect`, hello/welcome handshake, `CheckTransportSecurity` |
| `clients/codeblox/internal/command/auth.go` | `login` / `logout` / `list` / `status`, JSON reports |
| `clients/codeblox/internal/command/dispatch.go` | Subcommand + flag parsing, usage text |
| `clients/codeblox/internal/*/*_test.go` | Go tests across the four packages |

## Verification

**Unit — all Go tests green** (`go test ./...`), plus `go vet ./...` clean. Coverage includes each
precedence rung in isolation, the masking floor for short tokens, 0600 permissions on the file
store, backend selection and its error path, and the handshake against a real in-process websocket
server (not a mock).

**Live — against a controlled server requiring auth** (`createServer` on :7801 with
`authRequired: true`, valid token `the-only-valid-token`):

| Check | Result |
|---|---|
| `auth status` with nothing stored | `not authenticated — run codeblox auth login`, exit 1 |
| `auth login --with-token` | stored; output shows `the-…oken`, never the raw token |
| `auth status` with the **wrong** token | `server rejected the connection: unauthorized`, exit 1 |
| `auth status` with the **correct** token | `{"connected":true,…,"contract":true}`, exit 0 |
| `auth status --endpoint ws://build.example.com:7799` | refused before dialling; points at `wss://` |
| `auth logout` then `auth list` | credential removed; list reports none stored |

The happy path was additionally confirmed against the ordinary dev server on :7799. Binary size
9.3 MB; runs with no Node and no Python present.

## Notes / follow-ups

**Deviations from the plan document, and why.**

- **Env prefix is `CODEBLOX_`, not `CODEBOX_`.** The plan text says `CODEBOX_ENDPOINT` /
  `CODEBOX_PROFILE`, but `server/auth.js` already reads `CODEBLOX_TOKEN` and the package is named
  `codeblox`. `CODEBOX_` appears to be a typo carried from the repository name `vite-codebox`. The
  CLI uses `CODEBLOX_*` throughout so client and server agree.
- **No profiles.** The plan's config section describes `--profile`/`CODEBOX_PROFILE`, but its own
  Deferred section defers multi-profile auth, and the credentials rule makes a single active
  credential the baseline. Single credential implemented; profiles remain deferred.
- **`auth login` does not verify.** The credentials rule puts the live check on `auth status`, and
  verifying at login would fail the command whenever the server happens to be offline during setup.
  `login` stores and points the user at `auth status`.

**`auth status` cannot fully prove a token is valid.** A server started with `auth.required: false`
accepts any token, and the `welcome` frame carries no auth metadata, so the client cannot
distinguish "token accepted" from "server does not check tokens". `auth status` says so explicitly
rather than overclaiming. Adding an `authRequired` field to the `welcome` payload would make the
check conclusive — a small server-side change, deferred here because it touches the shared contract
and the viewer.

**WSS/TLS is still unbuilt** (see [phase-2.md](phase-2.md)). `CheckTransportSecurity` is the client
half of that gap: it refuses to send credentials in clear text to a remote host today, so the CLI is
already correct for the day the server gains TLS, and fails loudly until then.
