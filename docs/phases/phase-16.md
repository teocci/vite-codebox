# Phase 16 — The viewer applies agent direction, and an agent-set angle holds

- **Phase ID:** 16
- **Version:** (pending)
- **Date:** (pending)
- **Tests:** (pending)
- **Status:** 🚧 IN PROGRESS

## Objective

Make the five ops do something. Route them around the block engine via a new `onViewer` callback on
`WsClient`, turn every toggle into an idempotent setter because an agent cannot read viewer state
back, and add `hold` so an agent-set camera angle is preserved and refit as a build grows rather
than silently disabling the auto-framer for the remaining stages. Carries I-13.

## What was built

(fill during work)

## Files changed

| File | Change |
|---|---|

## Verification

(fill during work)
