# Phase 4 — Schema-driven build verbs — info, exec, and the ergonomic forms

- **Phase ID:** 4
- **Version:** 0.4.0
- **Date:** 2026-07-25
- **Tests:** 136
- **Status:** ✅ DONE (136 tests; live-verified).

## Objective

Make the CLI schema-driven rather than compiling the palette and protocol tables into the binary.
`info` fetches the `world_info` contract, prints it, and caches it under `~/.codeblox/`; every batch
is validated client-side against the fetched schema and palette so a bad material fails fast without
a round trip. Ships `exec` (JSON/NDJSON batch from stdin, the agent's main path), `materials`, the
ergonomic `box`/`sphere`/`cylinder` forms, `remove`, and `clear`, all able to emit compact JSON.

## What was built

**`internal/contract` — the server's vocabulary, held as data.** `Contract` models the published
`world_info` payload: `config` (block size, world bounds), `palette` (name → colour + render
family), and `ops` (each op's field-type map). Nothing about the world is compiled into the binary —
the op list and all 100 material names arrive from the server and are cached at
`~/.codeblox/world_info.json`. `ValidateCommand` walks the *published* field spec and checks arity
and integrality for `int3` / `int3+`, positivity for `int+`, non-negativity for `id`, and membership
for `material`. An unrecognised field type is deferred to the server rather than guessed at, so a
future server op does not require a client release. Extra fields are ignored, matching what the
server does.

**`internal/transport` — batch submission.** `SendBatch` writes a `commands` frame and returns the
server's `Ack`. The subtlety is ordering: the server broadcasts the resulting `diff` to *every*
subscriber before acking the sender, so a client that treated the first reply as its answer would
misreport every build. `awaitAck` reads past any non-ack frame, and treats an `error` frame as a
failure.

**`internal/command` — the verbs.** A `Session` interface (`Contract`, `SendBatch`, `Close`) now
sits between the verbs and the socket, so every verb is exercised in tests against a fake with no
network. `ParseBatch` accepts three shapes an agent might emit — a JSON array, a single JSON object,
or NDJSON with blank lines skipped. `RunBatch` is the shared path: resolve credentials, guard the
transport, connect, validate the whole batch, then send. `--dry-run` stops after validation.
`materials` reads the cache and never touches the network unless the cache is missing or
`--refresh` is given. The ergonomic `box`/`sphere`/`cylinder`/`remove`/`clear` forms build a single
command and route through the same validated path, so they cannot bypass a check `exec` enforces.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/internal/contract/contract.go` | Contract model, palette/op queries, schema validation, cache |
| `clients/codeblox/internal/transport/batch.go` | `SendBatch`, `Ack`, reading past broadcast diffs |
| `clients/codeblox/internal/transport/client.go` | `Contract()` accessor so `*Conn` satisfies `Session` |
| `clients/codeblox/internal/command/build.go` | `ParseBatch`, `ParseInt3`, `Exec`, `RunBatch`, `RunOne`, `Info`, `Materials` |
| `clients/codeblox/internal/command/dispatch_build.go` | Flags and routing for the world-facing verbs |
| `clients/codeblox/internal/command/dispatch.go` | New verbs in the router and usage text |
| `clients/codeblox/internal/command/auth.go` | `Session` interface; `Dial` returns it |
| `clients/codeblox/internal/config/config.go` | `ContractFileName` / `ContractPath` for the cache |
| `clients/codeblox/internal/*/*_test.go` | Go tests across the five packages |

## Verification

**Unit — all Go tests green** (`go test ./...`), `go vet ./...` clean, `gofmt` clean. Coverage
includes every field type and its failure mode, the ack-ordering case (a `diff` frame preceding the
ack), all three batch input shapes, and the cache-vs-fetch decision.

**Live — against a controlled server requiring auth** (`createServer` on :7801,
`authRequired: true`):

| Check | Result |
|---|---|
| `info` | printed block size 0.02 m (2 cm), bounds ±1600 / 3200 blocks, 100 materials, all 7 ops |
| contract cached | `~/.codeblox/world_info.json` written |
| `materials --family metal` | `brass`, `bronze`, `copper`, `copper_verdigris`, … from the cache with no dial |
| `exec` with `mat:"unobtanium"` | rejected client-side, **nothing sent**, exit 1 |
| `exec --dry-run` | reported valid, sent nothing |
| `exec` NDJSON bridge (clear + deck + 2 piers + dome) | `{"ok":true,"sent":5,"addedIds":[1,2,3,4],"cleared":true}` |
| `box --at 0,20,0 --size 4,4,4 --mat gold` | `{"ok":true,"sent":1,"addedIds":[5]}` |
| `box --at 999999,0,0` | server rejected: `part is out of world bounds`, exit 1 |
| `remove --id 1` / `clear` | `{"removed":[1]}` / `{"cleared":true}` |

## Notes / follow-ups

**Bounds are deliberately not checked client-side.** The plan asks for validation against "fetched
schema + palette", and that is exactly what is implemented. The published `fields` spec says `at` is
an `int3`, but not that it means a *min corner* for `box` and a *centre* for `sphere` — those
semantics live in `shared/protocol.js`'s normalisation. Implementing bounds in Go would mean
duplicating that geometry, which is the compiled-in knowledge this design exists to avoid. The
server stays the authority and reports out-of-bounds parts in its ack; the live check above confirms
that path works and surfaces a non-zero exit.

**`fill` has no ergonomic form.** The server publishes it and `exec` can send it, but there is no
`codeblox fill` verb — the plan lists only `box`/`sphere`/`cylinder` as ergonomic forms. Adding one
is trivial if the agent turns out to reach for it.

**The contract cache never expires.** `materials` serves from disk indefinitely; `--refresh` forces
a re-fetch, and every command-sending verb refreshes the cache as a side effect of connecting. If
the server's palette changes while an operator only ever runs `materials`, they would see a stale
list. A fetch timestamp plus a max age would fix it; deferred as it has no effect on correctness —
validation on any sending path always uses the freshly fetched contract.
