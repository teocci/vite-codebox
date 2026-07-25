# Improvements

Internal index of improvement items (`I-N`). Status is tracked inline in **Notes** — in progress
carries no done-marker; finalized appends `✅ Done in vX.Y.Z.` Detail files: `docs/improvements/`.

| ID | Idea | Notes |
|----|------|-------|
| I-1 | Per-verb flag validation | One shared `FlagSet` gave all 14 flags to all 8 verbs, so a foreign flag parsed clean and was ignored; `exec batch.json --json` dropped `--json` and exited 0. Per-verb surfaces + positional guard + validation before the keyring opens. Framework evaluated and declined — stdlib won all three rubrics. Detail: `docs/improvements/improvement-1.md`. ✅ Done in v0.5.0. |
| I-2 | Machine-readable failure contract | Every failure exited 1, so a wrapper could not tell "not authenticated" (re-auth) from "unreachable" (retry) from "bad material" (re-plan). Taxonomy 0/2/3/4/5/6 via a `Failure` wrapper whose innermost classification wins and survives `%w`; `--json` failures now emit a `{ok,code,exit,detail}` envelope on stderr; bare `codeblox` exits 2 on stderr. Detail: `docs/improvements/improvement-2.md`. ✅ Done in v0.5.0. |
| I-4 | Split `App` along its two domains | `App` carries 9 public methods spanning unrelated concerns — credential lifecycle (`Login`/`Logout`/`List`/`Status`) and world building (`Exec`/`RunOne`/`RunBatch`/`Info`/`Materials`) — sharing only `Env`, the streams, and `Dial`. At the ~7–10 god-object ceiling. The seam is already drawn by `auth.go` / `build.go`: two types over a small embedded struct. Fold in `App.Status`, which is 50 lines. Hygiene, not a defect — deliberately deferred until after P-5 so it does not tangle with new work. Planned. |
| I-3 | End-to-end test harness | Unit tests call Go functions and never spawn a process, so stream separation and exit codes were uncovered — the two things P-5's wrappers branch on. `clients/codeblox/tests/` drives the built binary behind `//go:build integration`, hermetic (temp home, file backend), skipping when no server listens. Detail: `docs/improvements/improvement-3.md`. ✅ Done in v0.5.0. |
