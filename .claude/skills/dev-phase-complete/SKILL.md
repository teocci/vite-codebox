---
name: dev-phase-complete
description: Finalize a completed phase and, when it closes a release group, cut the release — stamp detail files, update indexes, roll CHANGELOG, bump the version, index the release, commit, tag, and push. Use when the user says "phase complete", "finalize phase", "release this phase", "ship it", or "commit this fix". Run after all tests pass and live testing is done.
---

# dev-phase-complete

Finalize one completed phase (Part A), and when that phase closes its release group in `PLAN.md`,
cut the release (Part B). Deterministic bookkeeping runs in `scripts/`; you write the prose.

> **Scope — product releases only.** This skill bumps `__version__`, rolls `CHANGELOG.md`, and
> tags. Use it **only** for shipped-product iterations (a phase). **Everything under `.claude/`
> (skills, `rules/`, `settings.json`, hooks), meta-docs, and CI is chore-track** — do **not** run
> this on it; commit plainly with a Conventional Commit (`chore:`/`docs:`/`ci:`), no version bump
> or tag. See the release-track-vs-chore-track rule in
> `../dev-phase-workflow/references/conventions.md` §6b.

**Read first:** the base conventions at `../dev-phase-workflow/references/conventions.md` and the project
overrides at `docs/conventions/tracking.md`. Do **not** restate paths/formats here — they live there.

**Shared library:** the scripts import `tracklib` from the `dev-phase-lib` skill via a uniform bootstrap
— see `../dev-phase-lib/SKILL.md`.

## Preconditions
- All tests pass: run the project `<TEST_CMD>` from `tracking.md`. **Never finalize on red.**
- The phase's code + live testing are done.
- Know: the phase id, its item ids, the theme, and (for a release) whether this phase closes its release group.

## Part A — finalize the phase (always)
1. **Write the prose** the scripts can't: fill each item's detail file body (`docs/improvements/I-N.md` / `docs/fixes/F-N.md`) and the phase detail file (`docs/phases/phase-N.md`) — Objective/Approach or Symptom/Root cause/Fix, the Files-changed table, Verification. Leave the frontmatter `Status/Version/Date` as-is; Part B stamps them.
2. **Append CHANGELOG `[Unreleased]` bullets** — id-prefixed, in the right `### Added/Changed/Fixed` bucket (see conventions §6.4).
3. **Mark the phase done** (mechanical):
   ```bash
   $VENV/python .claude/skills/dev-phase-complete/scripts/finalize_phase.py P-<N>
   ```
   Flips the phase status to `done` in `PLAN.md` and `PROGRESS.md`. Add the reverse-chron
   `> Phase N (done): …` narrative blockquote to `PROGRESS.md` yourself (prose).

If this phase does **not** close its release group (batched cadence), stop here — the release comes when the last phase in the group finishes.

## Part B — cut the release (only when this phase closes its release group)
> **Branch precondition (conventions §7b):** the release tag is cut on `<RELEASE_BRANCH>`. In
> `branch` mode you finalize on the plan branch (steps 4–6) and **integrate to `<RELEASE_BRANCH>` in
> step 7**; in `trunk` mode you are already on `<RELEASE_BRANCH>`. Do the coherence gate (step 6) on
> the plan branch, before the switch.

4. **Compute the version** off the current `__version__` using the map (conventions §5): any improvement/feature/greenfield phase in the release → **minor**; fix-only → **patch**; a fix riding an improvement inherits the minor.
5. **Run the release bookkeeping** (bumps `<VERSION_FILE>` only — never `pyproject.toml`; rolls CHANGELOG; prepends the RELEASE.md row; stamps every detail file; done-marks the item indexes; marks PLAN rows `released`; updates PROGRESS `**Current version:**`):
   ```bash
   $VENV/python .claude/skills/dev-phase-complete/scripts/cut_release.py \
     --version X.Y.Z --date <YYYY-MM-DD> --tests <N> --theme "<one-line>" \
     --phases P-<N> [P-<M> …] --improvements I-a [I-b …] --fixes F-c [F-d …]
   ```
   Update the `PROGRESS.md` `**Active phase:**` header line yourself (prose).
6. **Coherence gate** — must pass before you commit:
   ```bash
   $VENV/python .claude/skills/dev-phase-status/scripts/check_coherence.py
   ```
   Also grep the staged diff for secrets (key/secret/token/password/passphrase).
7. **Integrate, tag, push** (base conventions §7 + §7b — never add `Co-Authored-By`; keep
   `.claude/settings.json` staged). **A release tag is cut only on `<RELEASE_BRANCH>` (`main`).**

   **`integration = branch` (this repo)** — commit the release on the plan branch, then integrate
   into `main` and tag *there*:
   ```bash
   # on the plan branch — commit the release bookkeeping
   git add -A
   git commit -m "release: vX.Y.Z — <theme> (IDs)"
   # integrate into main (fast-forward keeps history linear, matching this repo's tags)
   git switch main
   git merge --ff-only feat/<slug>     # if this FAILS, main diverged (e.g. a hotfix landed):
                                       #   git switch feat/<slug> && git merge main   # reconcile + re-plan if the version moved
                                       #   then retry: git switch main && git merge --ff-only feat/<slug>
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z              # triggers .github/workflows/release.yml
   git switch feat/<slug>             # resume the plan (branch == main after a ff)
   ```
   **`integration = trunk`** — you are already on `<RELEASE_BRANCH>`; commit, `git tag vX.Y.Z`, and
   `git push origin <RELEASE_BRANCH>` + the tag directly (no plan branch, no merge).

## Verification checklist
- [ ] `test_cmd` green before any edit
- [ ] Each item + phase detail file has a full body and (after Part B) `✅ DONE` + real version
- [ ] `CHANGELOG.md` has the rolled `## [X.Y.Z]` block and a fresh empty `## [Unreleased]`
- [ ] `docs/RELEASE.md` has the new release row on top
- [ ] `<VERSION_FILE>` `__version__` == the new version; `pyproject.toml` untouched
- [ ] `check_coherence.py` exits 0
- [ ] `PLAN.md` rows for the release are `released`; `PROGRESS.md` `**Current version:**` updated
- [ ] Release integrated to `<RELEASE_BRANCH>` and the tag `vX.Y.Z` cut **there** (not on the plan
      branch); `<RELEASE_BRANCH>` HEAD == this release
- [ ] Commit `release: vX.Y.Z — <theme> (IDs)`, `<RELEASE_BRANCH>` + tag pushed; no `Co-Authored-By`

## Notes
- Scripts do the mechanics; you supply judgment/prose (detail bodies, changelog wording, theme, commit message).
- If a script reports a table/section it can't find, the file format drifted — reconcile with `tracking.md` before hand-editing.
- To advance to the next phase after a release, use the `dev-phase-workflow` skill (type **NEXT**).
