# Phase 20 — Fast slash commands for the codeblox CLI

- **Phase ID:** 20
- **Version:** 0.10.0
- **Date:** 2026-07-29
- **Tests:** 552
- **Status:** ✅ DONE (552 tests; live-verified).

## Objective

Three operations recur throughout every build loop — wipe the world, move the camera, find out why
nothing is responding — and each one costs a full round trip today: recall where the binary is,
construct the invocation, call Bash. Put them behind `/codeblox:clear`, `/codeblox:view` and
`/codeblox:doctor`, executed at prompt expansion so they cost no deliberation and raise no
permission prompt. Wrap the CLI; do not duplicate what `codeblox-builder` already owns.

## What was built

One item, I-16: `cli.py` plus the three `/codeblox:*` command files. The detail lives in
[I-16](../improvements/I-16.md); what belongs at phase level is the scope call.

Three commands, and the list of what was left out is the substance of the decision. No `/box`,
`/sphere` or `/cylinder` — each invocation pays a fresh WS handshake and re-downloads the whole
world snapshot, so one shape per process is exactly the slow path `build.py` exists to avoid, and a
command would make the wrong habit convenient. No `/build`: `codeblox-builder` owns plan→batch, and
a second entry point is how the two drift. No `/info` (5 KB of contract JSON nobody acts on), no
`/remove --id N` (you never know a part id by hand), no `/materials` (the skill fetches it during a
build). What is left is what recurs in the loop and is not already one keystroke: wipe, aim, triage.

The permissions constraint shaped the implementation more than the feature did.
`.claude/settings.json` already allowlists `Bash(.venv/Scripts/python .claude/skills/*)`, so routing
through a skill script costs **no new permission entry**, while a hardcoded binary path would have
needed one. That is also why the venv interpreter is written out literally rather than picked at
runtime: a `[ -x … ] &&` prefix falls outside the allowlist pattern and would restore a prompt on
every call, which is the one thing these commands exist to avoid.

## Files changed

| File | Change |
|---|---|
| `.claude/commands/codeblox/{clear,view,doctor}.md` | New. The three commands; one `!` pre-execution line each. |
| `.claude/skills/codeblox-builder/scripts/cli.py` | New. Flagless passthrough to the resolved binary. |
| `.claude/skills/codeblox-builder/tests/test_cli.py` | New, 10 tests. |
| `.claude/skills/codeblox-builder/SKILL.md` | `cli.py` in "Running the scripts". |
| `.codex/…`, `.agents/…` | Mirrors propagated, chore track. |

`.claude/commands/` is new to this repo — the namespace was empty before this phase.

## Verification

277 pytest passed, 1 skipped (+10). `npm test` 126 passed. `mirror_skill.py --check` clean.

Live: all three commands exercised against the running server, both refusals confirmed to carry the
CLI's own message with no Python traceback, and the server-down path reproduced with
`npm run dev:stop` → `doctor.py` exit 4 → `npm start` → three `[ok  ]` rows. Full output in
[I-16](../improvements/I-16.md).
