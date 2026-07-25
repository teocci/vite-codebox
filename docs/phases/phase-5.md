# Phase 5 — codeblox-builder agent skill

- **Phase ID:** 5
- **Version:** 0.5.0
- **Date:** 2026-07-26
- **Tests:** 107 Go unit · 27 Go e2e · 104 skill (pytest) · 59 vitest — 297 total
- **Status:** ✅ DONE (297 tests; live-verified).

## Objective

Write the skill that lets an agent build from a prompt: discovery through
`codeblox info` rather than hard-coded tables, the op vocabulary, batching, the
coordinate convention, worked examples, and guardrails.

Two corrections shaped the delivery. The binary must not be hard-coded, so it is
resolved at runtime and an installer puts it on the User environment. And the
skill is **script-first**: every mechanical step is a tested script, because a
step left as prose is re-derived probabilistically on every run.

## What was built

`.claude/skills/codeblox-builder/` — six scripts, a test suite, and a SKILL.md
that carries only what needs judgment. Each script exists to remove one specific
probabilistic failure; anything that removed none was not written.

| Script | Removes |
|---|---|
| `resolve_codeblox.py` | guessing the binary path — `--bin`, `$CODEBLOX_BIN`, `$PATH`, then a dev checkout, each proved with `codeblox version` |
| `install_codeblox.py` | improvised registry edits — build, install, User PATH + `CODEBLOX_BIN`, with `--dry-run` and `--uninstall` |
| `doctor.py` | improvised diagnosis — binary, credential, server in one pass, exiting with the taxonomy code for the broken rung |
| `world.py` | re-parsing the contract — a token-small digest, and the anchoring rule |
| `shapes.py` | coordinate arithmetic — `shell`, `stairs`, `arch`, `bridge` generators |
| `submit.py` | the validate → send → parse-ack dance, and self-enforced bounds |

A named-but-missing `--bin` or `$CODEBLOX_BIN` is a hard error rather than a
fall-through: running a different binary than the operator named is worse than
failing. Resolution mirrors `config.Endpoint`'s precedence, so the CLI and the
skill resolve things the same way.

Injection points default to `None` and are resolved inside the function, not in
the signature. A signature default binds at definition time, so the seam would
silently ignore a later patch — the tests caught this immediately.

### The anchoring rule has exactly one home

`world.py` owns it, and `shapes.py` and `submit.py` import it. It is the one
piece of geometry `world_info` does **not** publish — the contract types fields,
it does not describe shapes — so it is the one thing at risk of drifting from the
server:

| op | `at` means |
|---|---|
| `box` | minimum corner |
| `sphere` | centre |
| `cylinder` | centre, **and the height is centred on it too** |

`TestAnchorConventionMatchesTheServer` guards it behaviourally rather than
textually: a part whose computed AABB rests exactly on the floor must be
accepted, and the same part one block lower must be refused. If the server ever
derived extent from `at` differently, one of those flips.

### PATH safety

The installer reads `HKCU\Environment` through `winreg`, which returns the raw
stored value and its type. `os.environ['PATH']` is never read — it is the machine
PATH merged with the user's, and writing that back to User scope would
permanently copy every machine entry into the user's own. `REG_EXPAND_SZ` is
preserved so `%USERPROFILE%`-style entries stay references, and the append is
performed on the raw string so every original character survives, including a
trailing separator. Planning and applying are separate, which is what makes
`--dry-run` report the exact before/after a real run would produce.

## Three bugs found while building

- **`npm run build:cli` produced an extensionless binary on Windows.** `go build
  -o bin/codeblox` writes exactly that name; `where.exe` cannot find it and
  CreateProcess will not launch it. A stale `codeblox.exe` sat beside it and the
  resolver picked the stale one. Fixed to `go build -o bin/` — given a directory,
  Go names the artifact and appends `.exe`.
- **`auth status` returned an unclassified exit 1.** I-2 classified the build
  path but `App.Status` repeated the same four steps unclassified. Both now go
  through one `App.connect`, which removes the duplication and the gap together.
- **`--at -20,0,-3` failed to parse.** argparse reads a leading `-` as an option
  and `-20,0,-3` is not a plain negative number. Half the world has negative
  coordinates, so this would have failed constantly; argv is now glued before
  parsing, and both `--at -20,0,-3` and `--at=-20,0,-3` work.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/SKILL.md` | new — the skill: pipeline, coordinates, design judgment, guardrails |
| `.claude/skills/codeblox-builder/scripts/*.py` | new — the six scripts above |
| `.claude/skills/codeblox-builder/tests/*.py` | new — 104 tests + conftest |
| `clients/codeblox/tests/world_test.go` | anchor-drift guard filled in |
| `clients/codeblox/internal/command/build.go`, `auth.go` | `App.connect` extracted; `auth status` classified |
| `clients/codeblox/internal/command/dispatch.go` | `Version` 0.3.0 → 0.5.0 |
| `package.json` | `build:cli` emits a correctly named binary |

## Verification

- **297 tests green**: 107 Go unit, 27 Go e2e (live server), 104 pytest, 59 vitest.
  `gofmt` and `go vet` clean on both tag sets.
- Resolver exercised at every rung, including from outside the repo, with a bogus
  `$CODEBLOX_BIN` failing hard rather than falling through.
- `install_codeblox.py --dry-run` against the real registry: 20 entries before,
  21 after, the original preserved byte-for-byte with exactly one appended.
- `doctor.py` returns 0 healthy, 3 with no credential, 4 with the server down.
- Built a real scene end to end against a live server — a 40-block bridge with
  piers and railings, a marble arch, and a solid staircase — 25 parts, ids 1–25.
- Bounds gate refuses a below-floor batch with per-command, per-axis detail and
  exit 5, sending nothing.

## Not done

The installer was never run for real — only `--dry-run`. Writing to the User PATH
is the one irreversible-ish step in the plan and is left for the operator to
trigger deliberately with `npm run install:cli`. Everything else works today
through the repo-checkout rung of the resolver.

POSIX install is deferred: `install_codeblox.py` reports what to do by hand
rather than editing shell profiles.
