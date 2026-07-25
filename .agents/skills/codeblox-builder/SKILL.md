---
name: codeblox-builder
description: Build structures in a codeblox world from a prompt — resolve the CLI, discover the live contract, generate exact block coordinates, and submit a validated batch. Use when asked to build, place, or remove anything in codeblox, or to inspect the world's materials, ops, or bounds.
---

# codeblox-builder

You design; the scripts compute. Everything mechanical — finding the binary,
reading the contract, coordinate arithmetic, bounds checking, submitting — is a
script under `scripts/`. What is left for you is the part a script cannot do:
deciding **what to build** and **what it should look like**.

Do not re-derive any of the below by hand. If you find yourself computing block
positions in your head, stop and use `shapes.py`.

## Running the scripts

All are stdlib Python, run through the repo's venv:

```
.venv/Scripts/python .claude/skills/codeblox-builder/scripts/<script>.py   # Windows
.venv/bin/python     .claude/skills/codeblox-builder/scripts/<script>.py   # POSIX
```

Never write a path to the `codeblox` binary anywhere. `resolve_codeblox.py`
finds it — an explicit `--bin`, then `$CODEBLOX_BIN`, then `$PATH`, then a repo
checkout — and every other script calls it for you.

## The pipeline

```
doctor.py            is everything working?        run once, first
world.py             what can I build with?        materials, ops, bounds
   ↓ you decide what to build
shapes.py <gen>      exact coordinates             NDJSON on stdout
   | submit.py       gate, validate, send          addedIds on success
```

### 1. Preflight

```bash
doctor.py
```

Checks the binary, the credential, and the server in one pass. Exit `0` means
go. Otherwise **report what it says and stop** — do not improvise a diagnosis:

| exit | meaning | what to do |
|---|---|---|
| 2 | binary not found | `npm run install:cli`, or set `$CODEBLOX_BIN` |
| 3 | not authenticated | `codeblox auth login` |
| 4 | server unreachable | start it with `npm start`, or fix the endpoint |

### 2. Discover — never assume

```bash
world.py            # digest: bounds, ops, materials grouped by family
world.py --json     # same, machine-readable
```

Material names and op names are **not** listed in this file, deliberately. They
come from the server at runtime, so a new material needs no change here. Use only
names `world.py` reports.

Materials are grouped by render family — `opaque`, `glass`, `metal`, `emissive`.
The family is usually what you actually want ("something glassy"); pick a
specific name from it.

### 3. Generate

```bash
shapes.py bridge  --at 0,0,0 --span 40 --width 6 --deck-height 8 \
                  --mat oak --pier-mat granite --rail-mat oak_dark
shapes.py shell   --at 0,0,0 --size 20,12,16 --thickness 1 --mat brick
shapes.py stairs  --at 0,0,0 --steps 8 --rise 1 --run 2 --width 3 --mat slate --solid
shapes.py arch    --at 0,0,0 --span 16 --rise 6 --mat marble
```

Each writes NDJSON to stdout. Negative coordinates work bare (`--at -20,0,-3`);
no `=` needed.

For anything the generators do not cover, write the commands yourself as NDJSON
and pipe them to `submit.py` — you are not restricted to these four shapes.

### 4. Submit

```bash
shapes.py bridge --span 40 --mat oak | submit.py
shapes.py bridge --span 40 --mat oak | submit.py --dry-run   # validate only
```

Reports `addedIds` on success. On failure the exit code tells you what kind:
`5` means it was rejected before anything was sent (fix and retry safely),
`6` means the server refused it.

`submit.py --dry-run` is a full check: it gates bounds itself, then asks the CLI
to validate types and materials. Note that `codeblox exec --dry-run` on its own
is **not** — the published schema types fields and says nothing about geometry,
so bounds are only evaluated once a batch is actually sent. Use `submit.py`.

## Coordinates

One block is the unit. `world.py` reports the buildable range; note that **y
starts at 0** — the floor — while x and z are symmetric about the origin. Nothing
may be built below y=0.

Anchoring differs per op, and `shapes.py` already handles it. You only need this
when hand-writing commands:

| op | `at` means |
|---|---|
| `box` | the **minimum corner** — the box grows toward +x, +y, +z |
| `sphere` | the **centre** |
| `cylinder` | the **centre**, and the height is centred on it too |

That last row is the easy mistake: a `box` at y=10 sits *on* y=10, but a
`cylinder` at y=10 with height 8 spans y=6 to y=14.

## Judgment — what is actually yours

**Prefer few large parts.** One `box` of 40×1×6 is one object in the engine; forty
1×1×6 boxes are forty. Both look the same and one is 40× the cost. Reach for a
larger part before a loop.

**Choose materials by family, then by name.** Structure reads better when the
family carries meaning — `metal` for supports, `glass` where light should pass,
`emissive` sparingly, as accents. A build using one material everywhere reads as
untextured.

**Give a structure proportion.** A bridge with a deck at 8 blocks and a 40-block
span reads right; the same deck at 40 blocks reads as a tower. When the prompt
does not specify, pick proportions that make the thing recognisable, and say what
you picked.

**Compose.** A castle is `shell` walls, `stairs` to the rampart, and `arch` for
the gate. Build the pieces, submit them as separate batches, and check the viewer
between them.

## Guardrails

- **Only material and op names `world.py` reports.** Anything else is refused
  before it is sent (exit 5).
- **Stay inside the bounds `world.py` reports.** `submit.py` gates this, but the
  gate is a safety net, not a design tool — plan inside the world.
- **Bounds are enforced by the server, not the schema.** The published contract
  types fields; it does not describe geometry. So a shape can be perfectly valid
  and still be refused for where it is (exit 6).
- **`clear` removes everything.** Confirm before using it on a world you did not
  just build.

## When something fails

Read the exit code first. Every script uses the CLI's taxonomy: `2` your
invocation, `3` credentials, `4` the server, `5` rejected before sending, `6`
rejected by the server. With `--json`, failures are a single-line envelope —
`{"ok":false,"code":...,"exit":N,"detail":...}` — so parse rather than match
prose.

If a script's own output is confusing, run it with `--json` and read the
structured form before guessing.
