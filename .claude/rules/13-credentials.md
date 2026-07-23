# Credential Management (API Auth)

## Applies When

This rule applies **only to tools that authenticate to an external API or service on the user's
behalf** — a CEX client, a cloud provider, a GitHub-style API. If the tool needs no credentials,
this rule does not apply; manage ordinary settings per [04-no-hardcoding.md](04-no-hardcoding.md).

**Skills are not CLI tools.** A skill needing an API key (e.g. a Gemini TTS skill) does **not**
implement the `auth login/logout/list/status` subcommands or a keyring lifecycle — that
architecture is for the host CLI tool, not a skill script. For skills, only the **Invariants**
below apply: read secrets from env-vars or the OS keyring, never hardcode/commit/log them, and mask
in output. See [15-skills.md](15-skills.md).

## Credentials Live Behind `<tool> auth` Subcommands

Model the `gh` CLI. Do **not** make the user hand-edit a `.env` or config file to authenticate.
Provide a credential lifecycle as first-class commands:

- `auth login` — add/update credentials. Interactive prompt by default (secret via a
  **hidden, no-echo prompt**). For automation, accept the secret however suits the tool — stdin,
  an env var, or flags (`--with-token`, `--key`/`--secret`, etc.); `gh auth login --with-token` is
  just one example. Prefer stdin or env where practical, since flag values can be captured in shell
  history, process listings, and CI logs.
- `auth logout` — remove the stored credentials.
- `auth list` — list stored credentials with secrets masked.
- `auth status` — show what is authenticated and run a **live** credential check.

A single active credential set is the baseline — a tool that authenticates one account needs
nothing more than the four commands above.

### Multi-Profile Support Is Optional

Profiles are a **login-level concept** — each profile *is* a distinct login/account. Add them
**only in the special case where authentication itself is multi-account** (the user logs into more
than one account and must switch); don't add them otherwise. When you do:

- `auth login <name>` (or `--profile <name>`) both authenticates **and** registers/selects that
  profile in one step — no separate "create profile" command (mirrors
  `gh auth login --hostname <host>`). Omit the name to target the default profile.
- `auth use <name>` — switch the active profile.
- Offer a one-invocation override: a `--profile` flag **and** a `<TOOL>_PROFILE` env var.
- `auth list` shows an active marker and `auth logout` defaults to the active profile.

When profiles are **not** supported, read every mention of "the active profile" below as simply
"the stored credential".

## OS Keyring Is the Default Secret Backend

- Store secrets in the **OS keyring** (`keyring` package) under a service name (e.g. `<tool>`).
- Keep only **non-secret** profile metadata and the active pointer in a plaintext store
  (`auth.json`) — never the secrets themselves when using the keyring backend.
- Provide a **file backend fallback** (secrets inline in `auth.json`, best-effort `0600`) for
  headless/CI where no keyring exists. Make the backend selectable by flag (`--keyring` /
  `--no-keyring`) and env (`<TOOL>_AUTH_BACKEND`); default to keyring and fall back automatically
  when it is unavailable.

## Env-Vars Are a Fallback, Not the Primary Path

- `<TOOL>_API_KEY` / `<TOOL>_API_SECRET`-style vars resolve **only when no active profile supplies the
  secret** (CI/automation).
- `.env` + `python-dotenv` may still load **non-secret** overrides (host/endpoint, environment such
  as testnet-vs-prod, profile selection) — never as the primary credential path.

## Never Put Secrets in Config Files

- `config.toml` and other config files hold **only non-secret settings**.
- Secrets go to the keyring (or the file/env fallback) — never into committed or
  machine-rewritten config.

## Secret Resolution Precedence

1. Active/selected auth profile — `api_key`, `api_secret`, plus any provider-specific secret
   (e.g. a passphrase).
2. Environment-variable fallback.

## Invariants (Always)

- Never log, print, or commit secrets; mask in any output (`key[:4]…key[-4:]`).
- `.gitignore` must cover `.env`, `.env.*`, `*.pem`, `*.key`, `*_key.json`, `secrets/`,
  `credentials/` — and the file-backend store (`auth.json`) when it may hold inline secrets.
- Set restrictive permissions (`600`/`700`) on any file holding sensitive data.
