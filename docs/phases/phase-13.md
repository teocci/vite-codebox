# Phase 13 — Stop world.py asking for a cache the CLI does not have

- **Phase ID:** 13
- **Version:** 0.8.0
- **Date:** 2026-07-27
- **Tests:** 488
- **Status:** ✅ DONE (488 tests; live-verified).

## Objective

Make the Python side describe the CLI it actually calls, so a refresh is either honest or absent —
and so a genuinely stale server stops being misreported as a stale cache.

Carries F-3 alone. Independent of P-14; either may run first, and they can run in parallel sessions.

## What was built

F-3, by deletion. `world.py` no longer offers `--refresh` at any level, because `codeblox info` has
no cache to bypass — it dials the server every call and only writes the contract file; `materials` is
the sole reader, which is why `materials` is the sole verb carrying the flag.

The more valuable half is the docstring. It had claimed both that `info` serves from the cache and
that `--refresh` forces a fetch, and neither was true — which is how a genuinely stale *server*
during P-9 was recorded as a stale *cache*, with a hand-deleted cache file as the remedy instead of a
restart. The docstring now names the real cause.

## Files changed

| File | Change |
|---|---|
| `.claude/skills/codeblox-builder/scripts/world.py` | `--refresh` removed from `fetch`, the argv, and the CLI; docstrings corrected |
| `.claude/skills/codeblox-builder/tests/test_world.py` | The mock-asserting refresh test replaced by two behavioural ones |

## Verification

484 tests: 91 vitest, 112 Go unit, 24 Go e2e, 257 pytest (+1 skipped). Live: the digest renders
against a running server, and `world.py --refresh` is refused by argparse rather than forwarded.

## Notes / follow-ups

- This edit makes the `.codex/` and `.agents/` copies of `world.py` one change staler. **P-14 (I-11)
  is what closes that**, and its drift test would have caught this the moment it landed.
- The Go side was left alone deliberately. `info`'s flag surface is correct as it stands; the
  asymmetry with `materials` reflects a real difference in what the two verbs do, not an oversight.
