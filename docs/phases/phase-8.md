# Phase 8 — Native ellipsoid and tube ops

- **Phase ID:** 8
- **Version:** 0.7.0
- **Date:** 2026-07-27
- **Tests:** 483
- **Status:** ✅ DONE (483 tests; live-verified).

## Objective

Give the model primitives that sculpt. A wheel is a cylinder about x, which the engine could not express, so the model reached for sphere — for wheels, paws and hands alike.

## What was built

I-7 — two new part ops, `ellipsoid` and `tube`, both additive to the wire protocol and both free on the Go side. Detail and the full rationale: `docs/improvements/I-7.md`.

## Files changed

| File | Change |
|---|---|
| `packages/shared/protocol.js` | two ops through `PART_OPS`, `OP_SCHEMA`, `toPart`, `validate` |
| `apps/web/src/engine/geometry.js` | two baked cylinder orientations |
| `tests/shared.test.js`, `tests/world.test.js` | op cases + a protocol/geometry parity guard |

## Verification

`npm test` — 74 passed (was 68). `go test ./...` unaffected: the CLI compiles in no op list, so the new vocabulary reaches it from the contract at runtime.
