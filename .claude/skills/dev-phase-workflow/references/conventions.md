# dev-phase-workflow conventions (reusable base)

The shared, **project-agnostic** methodology for the `dev-phase-*` skill family
(`dev-phase-start`, `dev-phase-status`, `dev-phase-complete`, `dev-phase-workflow`). ~80–90% of this transfers
unchanged to a new project. Anything project-specific (concrete file paths, the version-file
location, the test command, format deviations) lives in a project's
**`docs/conventions/tracking.md`**, which *overrides and extends* this file.

> **Resolution order (always):** base conventions (this file) → project `tracking.md` overrides.
> A script or skill reads the base rule, then applies any override keyed by the same name.
> If `tracking.md` is absent, the base applies as-is.

Placeholders written as `<NAME>` are defined by `tracking.md` (see
[Project bindings](#project-bindings-tracking-md-must-define)).

> **Running the scripts (`$VENV`):** every command shown as `$VENV/python …` resolves the venv
> binary once per session — `$VENV = .venv/Scripts` on Windows, `.venv/bin` on Linux/macOS. Call the
> binary by path; never `source activate` (see `.claude/rules/python-environment.md`).

---

## 1. The hierarchy

```
Release  vX.Y.Z   ── one or many phases ──▶  <CHANGELOG> (public) + <RELEASE_INDEX> (internal)
  └─ Phase  P-N    ── one or many items  ──▶  <PROGRESS> index + <PLAN> active plan
       └─ Item  I-N / F-N                ──▶  <IMPROVEMENTS> / <FIXES>
```

- **Release** — a versioned, published unit. One or many phases. Recorded publicly in
  `<CHANGELOG>` and indexed internally in `<RELEASE_INDEX>`.
- **Phase (`P-N`)** — the **unit of one working iteration** (see sizing below). One or many
  items, or greenfield build work with no items. Indexed in `<PROGRESS>`; planned in `<PLAN>`.
- **Item** — a single **improvement (`I-N`)** or **fix (`F-N`)** inside a phase. Indexed in
  `<IMPROVEMENTS>` / `<FIXES>`.

## 2. Phase-sizing heuristic (model-agnostic)

A phase must **fit comfortably in one working-context window with headroom** — small enough to
plan, implement, test, and finalize in a single iteration before context saturation degrades
quality. This is deliberately **not** a fixed token count: a larger-context model (e.g. 1M) may
carry a bigger phase than a 250K model. When decomposing:

- Split work so each phase is independently testable and finalizable.
- Prefer more small phases over one large phase; a phase you cannot finish in one sitting is too big.
- Greenfield: a phase is a coherent build slice (a subsystem/command). Post-prototype: a phase
  bundles one or a few small items that share a theme.

## 3. Lifecycle & skill responsibilities

| Stage | Skill | Mutates? | What happens |
|---|---|---|---|
| Decompose & order (plan mode) | `dev-phase-workflow` | no | Propose phase breakdown + execution order + parallel groups |
| Scaffold | `dev-phase-start` | docs only | Allocate ids, create detail stubs, index rows, write/extend `<PLAN>` |
| Observe | `dev-phase-status` | no | Report state + coherence; surface drift |
| Finalize a phase | `dev-phase-complete` (A) | docs | Fill details, mark done, accrue `<CHANGELOG>` Unreleased |
| Cut a release | `dev-phase-complete` (B) | docs + git | Bump version, roll changelog, index release; **integrate to `<RELEASE_BRANCH>` (branch mode)**, commit/tag/push there |
| Advance (NEXT) | `dev-phase-workflow` | `<PLAN>` cursor | Pick next unblocked phase(s); guard release boundaries; at plan-complete, drain/delete the branch (§7b) |

**Boundaries:** `dev-phase-start` never bumps/commits. `dev-phase-status` never mutates.
`dev-phase-workflow` never edits detail/index files — it routes and moves the cursor. Only
`dev-phase-complete` bumps the version, touches `<CHANGELOG>` version sections, or runs git. **Branch,
integration & concurrency policy is §7b** — the three guards (branch-off at plan-start, on-
`<RELEASE_BRANCH>` at release, drain-branch at plan-complete) live there; scripts only *detect*
branch state, runbooks *act*.

## 4. Division of labor: scripts vs model

Deterministic, mechanical work runs in a **script** (`<skill>/scripts/*.py`) to save tokens and
avoid drift; judgment/prose stays with the **model**.

- **Scripts:** id allocation, table-row insertion/updates, version bump, changelog roll, status
  parsing, topological ordering, coherence assertions.
- **Model:** phase decomposition, detail-file bodies (Objective/Approach/Symptom/…), changelog
  bullet wording, theme lines, commit messages.

Scripts read project bindings from `tracking.md` so the skill body stays portable.

## 5. ID schemes & version map

- Phases `P-<n>`, improvements `I-<n>`, fixes `F-<n>` — monotonic, **never reused**. Allocate the
  next free id by scanning the relevant index.
- **Version bump** off the current `<VERSION>` for a *release* (the union of its phases' items):
  - contains any improvement / feature / greenfield phase → **minor** (`x.Y.0`)
  - fix-only → **patch** (`x.y.Z`)
  - a fix riding with an improvement **inherits the minor** (no separate patch)
- SemVer, no pre-release/build tags unless `tracking.md` says otherwise.

## 6. Tracking files & templates

All internal files are written **token-efficiently for AI-agent consumption**. `<CHANGELOG>` is
the **only** human-facing/public file.

### 6.1 Item index rows
- **Improvements** (`<IMPROVEMENTS>`): `| ID | Idea | Notes |`; `ID` is a link
  `[I-N](improvements/I-N.md)`. Status is tracked **inline in Notes** — in progress carries no
  done-marker; finalized appends `✅ Done in vX.Y.Z.`
- **Fixes** (`<FIXES>`): `| ID | Symptom | Root cause | Fix | Phase |`; `ID` is a link. The last
  column holds the phase id or the release version; left blank until finalized.

### 6.2 Detail files
Frontmatter block (bold key list), then sections. In progress → `**Status:** 🚧 IN PROGRESS` and
`**Version:** (pending)`; finalized → `**Status:** ✅ DONE (NNN tests; live-verified).` with the
real version.

- **Improvement** `improvements/I-N.md`:
  ```markdown
  # I-N — <Title>

  - **Improvement ID:** I-N
  - **Version:** <version|(pending)>
  - **Date:** <YYYY-MM-DD>
  - **Status:** <🚧 IN PROGRESS | ✅ DONE (NNN tests; live-verified).>
  - **Related work:** <links to siblings / delivered fix>

  ## Objective
  ## Approach
  ## Files changed
  | File | Change |
  |---|---|

  ## Verification
  ```
- **Fix** `fixes/F-N.md`: same frontmatter with `**Fix ID:**`; sections
  `## Symptom` / `## Root cause` / `## Fix` / `## Files changed` (table) / `## Verification`.
- **Phase** `phases/phase-N.md` (retrospective style): frontmatter `**Phase ID:** / **Version:** /
  **Date:** / **Tests:**`, then `## Objective` / `## What was built` / `## Files changed` (table) /
  `## Verification` / optional `## Notes / follow-ups`.

### 6.3 `<PROGRESS>` (internal phase index)
- Header: `**Current version:**`, `**Active phase:**` (one-line prose naming the in-flight
  release + items + test count), pointer to detail files.
- **Phase status table:** `| Phase | Title | Status |` — status is lowercase prose
  (`planned` / `in progress` / `done`). **No emoji, no version column, no "Quick Status" table.**
- `## Next action` section.
- Reverse-chronological `> Phase N (done): …` blockquotes — one dense paragraph per finished
  phase (the resume narrative). Added by `dev-phase-complete`.

### 6.4 `<CHANGELOG>` (public — Keep a Changelog + SemVer)
- `## [Unreleased]` at top accrues bullets as phases finalize (Part A).
- A release promotes it to `## [X.Y.Z] - YYYY-MM-DD` with an optional theme paragraph and
  `### Added` / `### Changed` / `### Fixed` subsections; each bullet is **id-prefixed**
  (`- I-6: …`, `- F-5: …`). Leave a fresh empty `## [Unreleased]`.

### 6.5 `<PLAN>` (active plan ledger — internal)
```markdown
# Active Plan

**Approved:** <YYYY-MM-DD>  **Branch:** <branch>  **Cadence:** <per-phase | batched | note>

| Phase | Items    | Depends | Release | Version   | Status      |
|-------|----------|---------|---------|-----------|-------------|
| P-15  | I-5      | —       | R1      | 0.3.0     | released    |
| P-16  | I-6      | P-15    | R2      | (pending) | in-progress |
| P-17  | I-7, F-4 | P-15    | R3      | (pending) | pending     |
```
- `Status ∈ {pending, in-progress, done, released}`. `Depends` is `—` or a comma-list of phase ids.
- `Release` groups phases into releases (a shared tag = batched cadence; unique tags = per-phase).
- **Cursor** = the topmost row not yet `released` whose `Depends` are all `done`.
- When every row is `released`, reset the file to a `No active plan.` stub. That reset is the last
  step of the §7b drain, and the model runs it — no script does it.
- **The ledger may hold more than one plan.** Work discovered mid-flight is scaffolded as a second
  group of rows with its own `Release` tags; `Depends` orders the two groups against each other, and
  the cursor falls out of the DAG. `dev-phase-start` **appends** — it never rewrites a row it did not
  create — and refuses outright on a ledger that is fully `released` (drain it first) or that does
  not parse. So re-running scaffold against an active plan is safe and additive.

### 6.6 `<RELEASE_INDEX>` (release → phases, internal)
`| Release | Date | Phases | Theme |`, newest first. One row per cut release. The detailed
public notes live in `<CHANGELOG>`; this file is the terse index.

## 6b. Release track vs chore track (what does NOT get a release)

The phase → version → CHANGELOG → tag machinery governs **product iterations only**. Not every
commit is a release; forcing tooling/process work through `dev-phase-complete` would wrongly bump the
version and cut a tag.

- **Release track** → a phase, finalized/released by `dev-phase-complete` (version bump + `<CHANGELOG>`
  + `<RELEASE_INDEX>` row + tag). Use when the change is a **shipped-product iteration** a user or
  agent would see in release notes: product source behavior/CLI, packaging-as-a-deliverable,
  user-facing docs bundled with a version. Tracking-file edits made *while delivering a phase*
  (`<PLAN>`, detail stubs) ride the release commit — `dev-phase-complete` sweeps them via `git add -A`.
- **Chore track** → a plain **Conventional Commit**, with **no** version bump, **no** `<CHANGELOG>`
  entry, **no** `<RELEASE_INDEX>` row, **no** tag, **no** phase. Use for developer tooling and
  process. **As a rule, everything under `.claude/` is chore-track** — skills, `rules/`,
  `settings.json`, hooks, commands — because it is agent/dev configuration, never shipped product.
  Also chore-track: meta or planning docs, CI/build tweaks not tied to a release, and refactors
  with no user-visible effect. Commit types: `chore:` / `docs:` / `ci:` / `build:` / `refactor:` /
  `test:`. Path hints: `.claude/**` → `chore(...)`; meta docs → `docs`; `.github/**` → `ci:`.

**Decision rule:** *"Would this appear in product release notes, or change shipped behavior?"*
Yes → release track. No → chore track.

Chore commits never touch `<VERSION>` or the `<CHANGELOG>` version sections, so `check_coherence.py`
stays green across them — the two tracks do not interfere.

## 7. Commit & release convention

- Release commit: `release: vX.Y.Z — <theme> (IDs)` (em-dash; ids in parentheses).
- Other commits: Conventional Commits with an id scope where relevant
  (`fix(F-3): …`, `feat: Phase 12 — …`, `docs(...): …`).
- **Never** add `Co-Authored-By` or other AI trailers.
- Releases are **tag-driven**: after the release commit, `git tag vX.Y.Z` and push
  `<RELEASE_BRANCH>` + the tag. Pushing the tag is what triggers the release workflow. **Where the
  tag is cut** (directly, or after integrating a plan branch) is set by `integration` — see §7b.

## 7b. Branch, integration & concurrency model

Where commits and release tags land, and if/when a feature branch merges to the mainline, is a
**per-project policy** — not something the skills should assume silently. Three bindings encode it;
`tracking.md` sets the values (defaults: `release_branch = main`, `integration = trunk`,
`concurrency = single`). The **invariant every mode preserves:** `<RELEASE_BRANCH>` HEAD is the
**latest released truth** — a release tag is always cut on `<RELEASE_BRANCH>`.

### `integration` — how work reaches `<RELEASE_BRANCH>`
- **`trunk`** — commit and release directly on `<RELEASE_BRANCH>`; use short-lived branches only for
  risky work and merge them **before** releasing. Simplest; one line of development.
- **`branch`** — each plan runs on its own `feat/*` branch (recorded in `<PLAN>` `Branch:`).
  **The release *is* the integration:** to cut a release you switch to `<RELEASE_BRANCH>`, merge/FF
  the finished phase(s), tag there, push, **then the plan branch pulls `<RELEASE_BRANCH>` back**
  (to absorb its own version bump + `<CHANGELOG>` roll). This is continuous integration — merge
  little and often, keeping the branch short-lived; it is *not* "hoard tags on the branch, merge at
  the end" (a long-lived branch accrues integration debt).

### `concurrency` — how to have more than one thing checked out at once
- **`single`** — one working dir; `git switch` between branches (only one live at a time).
- **`worktree`** — every branch is its own `git worktree` (separate working dir sharing one repo).
- **`hybrid`** *(recommended when `integration = branch`)* — normal plans run on a branch in the
  **one** working dir; escalate to a worktree **on demand** for the two cases that need two things
  live at once: a **mid-plan hotfix** and **genuinely parallel phases** in separate sessions.
- **Python caveat (any worktree):** a worktree is a separate directory, so an editable install
  (`pip install -e`) points at *that worktree's* source. Each worktree needs its **own** venv +
  editable install, or code runs against the wrong tree. This is why worktrees are on-demand, not
  free — `tracking.md` states the concrete setup command.

### The three guards (portable; scripts only *detect*, runbooks *act*)
1. **plan-start** — never scaffold a plan while on `<RELEASE_BRANCH>` (in `branch` mode): create the
   plan's `feat/*` branch first and record it in `<PLAN>` `Branch:`. This is what makes parallel
   sessions safe. `dev-phase-start`'s script refuses with an actionable message; the model creates the
   branch (or worktree).
2. **release (Part B)** — must be on `<RELEASE_BRANCH>` to tag. In `branch` mode Part B integrates
   first (merge/FF the plan branch → `<RELEASE_BRANCH>`), then tags there.
3. **plan-complete** — by per-release integration the branch is already drained into
   `<RELEASE_BRANCH>` when the last row goes `released`; delete the merged branch and prune any
   worktree **before** resetting `<PLAN>` to the stub.

### Mid-plan hotfix pattern (`integration = branch`)
A bug found deep in a plan does **not** wait for the plan to finish: isolate it on
`<RELEASE_BRANCH>` (a worktree keeps the plan's work untouched in its own dir), fix + release it
there, then the plan branch pulls `<RELEASE_BRANCH>` to absorb the fix — re-planning between phases
if the version shifted. Git *mutation* here (worktree add/remove, merge, tag) is a runbook the model
runs; the scripts stay read-only.

## 8. Version bump mechanics

- The version lives in exactly one place, `<VERSION_FILE>` (`<VERSION_ATTR>`). Bump **only** there.
- If the project derives its package version dynamically from that attribute (common), **never**
  add a literal version elsewhere (e.g. a build file) — doing so is a bug. `tracking.md` states
  the specific hazard for the project.
- **The version file is language-agnostic.** The bump reads and writes both the assignment form
  (`<VERSION_ATTR> = '1.2.3'` — Python, JS) and the mapping form (`"<VERSION_ATTR>": "1.2.3"` —
  JSON, YAML), so a `package.json` is as valid a `<VERSION_FILE>` as a `src/__init__.py`. The
  value's **quote character is preserved**, which keeps JSON valid and stops a double-quoted
  Python file being reflowed on every release. The value must be quoted — a bare YAML scalar
  (`version: 1.2.3`) is not matched.
- **A bump that matches nothing is a hard failure**, not a no-op: `cut_release.py` exits naming
  `<VERSION_FILE>` and writes nothing. A silent skip would report a bump that never happened and
  leave the release incoherent (the coherence gate would then flag it as a CHANGELOG mismatch —
  late, after the other files are already rewritten, and pointing at the wrong file).

## 9. Guardrails

- **Tests green before any finalize.** Never finalize/release on a failing suite (`<TEST_CMD>`).
- **Coherence gate before commit/tag** (see `dev-phase-status/scripts/check_coherence.py`): version
  is semver; no forbidden literal version; top `<CHANGELOG>` heading == `<VERSION>`; released-group
  detail files are `✅ DONE` with matching version; `<RELEASE_INDEX>` top row == `<VERSION>`.
- **No secrets in the diff** (grep for key/secret/token/password/passphrase patterns).
- **No premature advance:** `dev-phase-workflow` refuses NEXT past a phase that closes a release group but
  isn't `released` yet.
- **Release on `<RELEASE_BRANCH>` (§7b):** a release tag is cut only on `<RELEASE_BRANCH>`; in
  `branch` mode Part B integrates first. `<RELEASE_BRANCH>` HEAD == latest release is an invariant
  (`check_coherence.py` asserts it when run on `<RELEASE_BRANCH>`).
- **No plan on `<RELEASE_BRANCH>` (branch mode):** `dev-phase-start` refuses to scaffold onto
  `<RELEASE_BRANCH>` — branch first.

## Project bindings (`tracking.md` must define)

| Placeholder | Meaning |
|---|---|
| `<PACKAGE>` | Import/package name |
| `<VERSION_FILE>` / `<VERSION_ATTR>` | The single version source-of-truth and the key inside it. Any language (§8): `src/__init__.py` + `__version__`, or `package.json` + `version`. `<VERSION_ATTR>` is the **bare key name** — no surrounding quotes, even for JSON. |
| `<TEST_CMD>` | Command that runs the suite |
| `<RELEASE_BRANCH>` | Branch a release tag is cut on (default `main`) |
| `integration` | `trunk` \| `branch` — how work reaches `<RELEASE_BRANCH>` (§7b; default `trunk`) |
| `concurrency` | `single` \| `worktree` \| `hybrid` — multiple checkouts at once (§7b; default `single`) |
| `<PROGRESS>` `<PLAN>` `<RELEASE_INDEX>` `<CHANGELOG>` `<IMPROVEMENTS>` `<FIXES>` | Concrete file paths |
| detail dirs | `phases/`, `improvements/`, `fixes/` locations |
| overrides | any format deviation or extra rule specific to the project |
