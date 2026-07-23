# File & Data Locations

## Applies When

This rule applies to any CLI tool that reads or writes **per-user config or data
files**, or resolves a path to them. It owns *where* files live and *how* a path is
discovered. For non-secret value resolution see [04-no-hardcoding.md](04-no-hardcoding.md);
for secrets see [13-credentials.md](13-credentials.md).

This rule does **not** apply to skills — a skill owns no per-user `~/.<tool>/` base dir. A skill's
scripts read/write within the skill directory, from passed arguments, or a scratch/temp dir. See
[15-skills.md](15-skills.md).

## Canonical Base Dir (Invariant)

- All per-user config and data live under a **single base dir**, `~/.<tool>/` (the
  same convention `gh` uses for `~/.config/gh`), resolved by **one helper**.
- **The location does not change between source and packaged (PyInstaller) runs.**
- **Never** branch path resolution on `sys.frozen`, `sys._MEIPASS`, or `__file__`.
  Never resolve user data relative to the bundle or the current working directory by
  default — the bundle is read-only and the CWD is arbitrary.

## Discovery Precedence (Honor It; Don't Reinvent)

- **Config file:** explicit `--config` flag → `$<TOOL>_CONFIG` env var →
  project-local config in the current working directory → `~/.<tool>/` config.
- **`.env`:** current working directory `.env` → base-dir `.env`; real OS
  environment variables always win over both.
- New commands and stores must resolve paths through the **existing config helpers**,
  not with ad-hoc `Path` lookups that reimplement (or diverge from) this order.

## Centralize Names

- Filenames, directory names, and `<TOOL>_*` env-var names live in **one constants
  module**. Add new ones there.
- Never hardcode a literal filename or path elsewhere in the codebase.

## Secrets vs Non-Secret Split

- Secrets (`.env`, the auth store) → [13-credentials.md](13-credentials.md).
- Non-secret value resolution (env → file → default) → [04-no-hardcoding.md](04-no-hardcoding.md).
- A plaintext config file holds **only non-secret settings** — never credentials.
