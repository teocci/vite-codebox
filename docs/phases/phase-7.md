# Phase 7 — Close the two silent holes under the scale gate

- **Phase ID:** 7
- **Version:** 0.7.0
- **Date:** 2026-07-27
- **Tests:** 483
- **Status:** ✅ DONE (483 tests; live-verified).

## Objective

Two latent defects that would each let the rest of this plan fail quietly. Neither is visible in normal use until the world grows.

## What was built

Two fixes, both found while planning the true-scale work rather than by hitting them, and both of a kind that fails quietly.

**F-1** — the CLI's welcome frame carries the whole world snapshot, and `SetReadLimit` was never called, so `coder/websocket`'s 32 KiB default capped the world at ~330 parts. Past that every command failed at the handshake, `clear` included, and the cached contract kept `doctor.py` reporting a healthy server. Never hit because the largest existing build is 52 parts; building at 1:1 crosses it with two builds.

**F-2** — `world.aabb()` fell through to `None` for any op it did not recognise, and `None` means "occupies nothing", so `fill` passed the client-side bounds gate unchecked. Fixed by inverting the default: an explicit `CONTROL_OPS` allowlist returns `None` and everything else must have a case or raise. That is the part that matters for the rest of the plan — P-9 measures a plan's extent through the same function, so an op invisible to it would be invisible to the scale gate too.

Details: `docs/fixes/F-1.md` · `docs/fixes/F-2.md`.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/internal/transport/client.go` | `ws.SetReadLimit(-1)` before the handshake |
| `clients/codeblox/internal/transport/client_test.go` | oversize-welcome test + fixture |
| `.claude/skills/codeblox-builder/scripts/world.py` | `CONTROL_OPS`, `AnchorError`, exhaustive `aabb()` |
| `.claude/skills/codeblox-builder/scripts/submit.py`, `scripts/build.py` | `AnchorError` → exit 5, ordered before `WorldError` |
| `.claude/skills/codeblox-builder/tests/test_world.py`, `tests/test_submit.py` | anchoring + exit-code cases |

## Verification

`go test ./...` green (5 packages). `python -m pytest .claude/skills/codeblox-builder/tests/` — 162 passed, 1 skipped.

F-1's test was confirmed non-vacuous by reverting the fix: it fails with `message too big: read limited at 32769 bytes` on an 83624-byte welcome.
