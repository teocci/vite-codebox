# Phase 14 — Make the skill mirrors provable rather than remembered

- **Phase ID:** 14
- **Version:** 0.8.0
- **Date:** 2026-07-27
- **Tests:** 488
- **Status:** ✅ DONE (488 tests; live-verified).

## Objective

Make mirror staleness impossible to ship unnoticed: generate `.codex/` and `.agents/` from the one
source in `.claude/`, fail a test when they drift, then sync them.

Carries I-11 alone. Independent of P-13; either may run first, and they can run in parallel sessions.

## What was built

I-11, and it closes R3. `scripts/sync-skills.mjs` regenerates both mirrors from
`.claude/skills/codeblox-builder`, and `tests/skill-mirrors.test.js` fails when they drift — the
second is the point. The mirrors went stale after P-7, P-9 and P-10 because nothing ever failed when
they did; a sync script alone would have been a fourth manual step to forget.

The mirrors stay committed rather than becoming generated-and-gitignored. Ignoring them would make
drift structurally impossible, but a mirror exists so another agent host can read the skill straight
from a checkout, and a generated mirror is missing exactly when it is wanted.

## Files changed

| File | Change |
|---|---|
| `scripts/sync-skills.mjs` | New — the sync, with a guard against an empty source |
| `tests/skill-mirrors.test.js` | New — four tests, file set and byte equality per mirror |
| `package.json` | `sync:skills` script |
| `.codex/skills/codeblox-builder/**`, `.agents/skills/codeblox-builder/**` | Synced — 13 rewritten, 3 added, each |

## Verification

488 tests: 95 vitest, 112 Go unit, 24 Go e2e, 257 pytest (+1 skipped). The drift test was seen
failing before the sync existed and again on a deliberately drifted file, then green after syncing;
`pytest` against the `.codex` mirror passes 257, so the copies are usable and not merely equal.

## Notes / follow-ups

- **`.agents/rules/` is orphaned and was left alone.** Twelve tracked files with no source in the
  repo (`.claude/` tracks only `settings.json` and `skills/`), whose names no longer match the global
  rule set they were presumably copied from. They cannot be synced from anything here. Worth an
  explicit decision — most likely deletion — but not one to make silently inside this item.
- `.codex/` carries no `rules/` at all, so the two hosts were never mirroring the same set.
- The sync is not wired into a commit hook or an npm lifecycle step. The test is the gate; adding a
  hook would enforce the same rule in a second place that could disagree with the first.
