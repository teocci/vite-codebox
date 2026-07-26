# Active Plan

**Approved:** 2026-07-26  **Branch:** main  **Cadence:** batched

| Phase | Items | Depends | Release | Version | Status |
|-------|-------|---------|---------|---------|--------|
| P-7 | F-1, F-2 | — | R2 | (pending) | done |
| P-8 | I-7 | P-7 | R2 | (pending) | done |
| P-9 | I-8 | P-7 | R2 | (pending) | done |
| P-10 | I-9 | P-8, P-9 | R2 | (pending) | pending |
| P-11 | I-10 | P-9 | R2 | (pending) | pending |
| P-12 | I-5, I-6 | — | R2 | (pending) | done |

## Handoff — 2026-07-26

P-7, P-8 and P-12 are implemented, tested, documented and **committed on `main`** (through
`9fd8ff7`), but **unreleased**: P-7 was originally scaffolded as its own release group R1 and was
then collapsed into R2, so everything ships together as one minor (`v0.7.0`) when P-11 closes the
group. The tag is still `v0.6.0` and `[Unreleased]` carries the bullets.

P-9 is **done** and unreleased with the rest. P-10 and P-11 are now a **parallel wave** — P-10 needs
P-8 and P-9, P-11 needs P-9, and both are satisfied — so they are independent and can run in separate
sessions. The full design for both is in the approved plan and in the `I-9` / `I-10` stubs.

P-11 has a number waiting for it: I-8's oversized-subject envelope asks for `world.extent` ≥ 1368.5
to hold the Golden Gate at 1:1, which is where P-11's `extent 1400` comes from.

Notes for `dev-phase-complete` Part B:

1. **The release tooling was briefly broken and is now fixed — take the upstream refresh, not
   any local patch.** Flattening the family to `.claude/skills/dev-phase-*/` replaced two
   files with pristine upstream copies, reverting version-handling fixes committed in
   `fe0b72f`. Both were generalised and accepted upstream in `llm-skill-crafting`, and the
   refresh has landed: `read_version` and `bump_version_text` now both live in `tracklib.py`
   and share one private `_version_pattern(attr)` builder, so the reader and the writer
   cannot drift. `check_coherence.py` is green and `dev-phase-lib/tests` is 44 passing, with
   read/bump coverage across Python single- and double-quote, JSON and quoted YAML plus a
   `read_version(bump_version_text(...))` round-trip — neither function had a test before.

   Two consequences worth knowing. The upstream pattern absorbs an optional key-quote into
   the separator group, so **`version_attr = 'version'` is now the correct binding for
   `package.json`**; `tracking.md:10` still carries the older workaround spelling
   `"\"version\""`, which continues to work (the change is a strict superset) but is no
   longer necessary — dropping the quotes there also means updating the prose at
   `tracking.md:38`. And unquoted YAML scalars (`version: 1.2.3`) remain unsupported by
   design; quote the value.
2. **Two version sites.** Per `docs/conventions/tracking.md`, a release must bump
   `package.json` *and* `command.Version` in
   `clients/codeblox/internal/command/dispatch.go`.

3. **P-12 is retroactive and carries no work.** I-5 and I-6 were implemented and committed
   (`8c99d21`, after the `v0.6.0` tag) outside the phase structure, so they had no row here
   and no path to a version. P-12 is that row, allocated after the fact and already `done`;
   the id is later than the work because ids are allocation order, not chronology. It is
   folded into **R2** rather than released on its own, because `_roll_changelog` moves the
   *whole* `[Unreleased]` body into the new block — cutting a v0.7.0 for I-5/I-6 alone would
   have swept P-7 and P-8's bullets into a release they do not belong to.

   Three things had to change before the tooling could see them at all, and each failed
   *silently*: the detail files were named `improvement-{5,6}.md`, but
   `cut_release.py` resolves `<improvements_dir>/<id>.md` behind an `if f.exists()` guard, so
   they were skipped rather than reported; their frontmatter was hand-written
   (`**Version:** unreleased`, `**Status:** complete, awaiting a release.`), which
   `_stamp_detail` cannot match since it rewrites only `(pending)` and `🚧 IN PROGRESS`; and
   `**Version:** unreleased` is invisible to `check_coherence.py`, which inspects only detail
   files whose version equals the *current* one — which is why the gate stayed green over a
   two-item hole. All three are now normalised. Pass `--improvements I-5 I-6` with the rest.

`dims.py` is complete as of P-9: tested, live-run, its inherited `factor` defect fixed and its WIP
banner removed. Two things it surfaced are **not** fixed and have no item yet:

- `world.fetch(refresh=True)` sends `--refresh` to `codeblox info`, which rejects it
  (`flag provided but not defined: -refresh`). So a refresh is a usage error and `doctor.py` can
  report a **stale cached contract** — the cache at `~/.codeblox/world_info.json` had to be deleted
  by hand to re-fetch. Wants a fix item.
- The running ws server is **stale**: a fresh fetch published only 8 ops, without P-8's `ellipsoid`
  and `tube`, though both are committed in `packages/shared/protocol.js`. Restart is all it needs,
  but I-7 has therefore not been live-verified against a server built from its own code.

The `codeblox-builder` skill has not been mirrored to `.codex/` or `.agents/`, so those two copies
are stale with respect to the P-7 changes in `world.py`, `submit.py` and `build.py` — and now the
P-9 changes in `build.py`, `world.py`, `doctor.py` and the new `dims.py`.
