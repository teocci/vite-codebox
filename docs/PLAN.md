# Active Plan

**Approved:** 2026-07-25  **Branch:** main  **Cadence:** per-phase

| Phase | Items | Depends | Release | Version | Status |
|-------|-------|---------|---------|---------|--------|
| P-3 | — | — | R1 | 0.3.0 | released |
| P-4 | — | P-3 | R2 | 0.4.0 | released |
| P-5 | I-1, I-3, I-2 | P-4 | R3 | 0.5.0 | released |

**This plan is closed.** All three phases shipped; v0.5.0 was the last release in it.

P-5 carried three prerequisite improvement items, worked before the skill itself, in this order:
**I-1** (per-verb flag validation), **I-3** (end-to-end test harness), and **I-2** (machine-readable
failure contract). All three hardened the binary the skill's Python wrappers parse, so they landed
first. I-3 came before I-2 deliberately: the harness is what proves I-2's exit-code taxonomy actually
reaches a caller, and it was built to make that tightening a one-constant change.

Carried forward, unscheduled: **I-4** (split `App` along its two domains) and **WSS/TLS**, the
Phase-2 follow-up that still blocks remote use.
