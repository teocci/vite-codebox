---
name: codeblox-builder
description: Use when asked to build, place, rebuild, or remove anything in a codeblox world — a structure, a scene, a single shape — or to inspect the world's materials, ops, or bounds.
---

# codeblox-builder

You design; the scripts compute. Everything mechanical — finding the binary, reading the contract, coordinate arithmetic, bounds checking, ordering, pacing, submitting — is a script under `scripts/`. What is left for you is the part a script cannot do: deciding **what to build**, **what it should look like**, and **in what order it should land**.

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

## The workflow

```
doctor.py            is everything working?         run once, first
world.py             what can I build with?         materials, ops, bounds
   ↓ you decide what to build, and in what order it lands
plan.json            stages, big to small           you write this
   | build.py        validate all, land beat by beat  progress per stage

shapes.py <gen>      one shape's coordinates        NDJSON on stdout
   | submit.py       gate, validate, send           addedIds on success
```

`build.py` is how you build a structure. `shapes.py | submit.py` is the quick path for a single shape you just want to drop in.

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

### 3. Plan the stages

**Build order is not bookkeeping — it is what the audience watches.** The viewer drops every newly added part in from six blocks up, staggered a few milliseconds apart, and a part that has settled never moves again. So each batch you submit is *one animation beat*. A structure sent as one flat batch lands as one undifferentiated shower; the same structure sent as five stages reads as something being built.

Work bottom-up, big to small:

| # | Stage | What lands |
|---|---|---|
| 1 | **Ground** | `world.py` to see the world, then a `clear` if you are replacing what is there |
| 2 | **Mass** | the big forms — the silhouette, in as few large parts as possible |
| 3 | **Structure** | towers, limbs, spans — what grows out of the mass |
| 4 | **Openings** | doors, windows, arches |
| 5 | **Detail** | finials, eyes, teeth, accents in a contrasting family |

**Openings are composed, not carved.** There is no boolean subtraction in this engine — geometry is scaled parts, and `remove` deletes a part *by id*, not a region. You cannot punch a hole in a wall. Build the wall as parts arranged *around* the gap instead, which is what `shell` already does internally. If you find yourself wanting to subtract, you placed the mass too coarsely one stage earlier.

A plan is one JSON object, and it is worth keeping — the whole build is reproducible from it, and re-running one stage beats rebuilding from scratch. Write it to `builds/<name>.json` rather than leaving it loose in the project root. That directory is the working space for plans and is not tracked, so treat it as yours to fill. Each part is either a **shape call** (expanded through the generators below) or a **raw command** passed through untouched:

```json
{
  "name": "castle",
  "stages": [
    { "name": "ground", "parts": [ {"op": "clear"} ] },
    { "name": "mass",   "parts": [
        {"shape": "shell", "at": [-20,0,-20], "size": [40,14,40], "mat": "brick", "thickness": 2} ] },
    { "name": "towers", "parts": [
        {"shape": "shell", "at": [-22,0,-22], "size": [6,22,6], "mat": "granite"},
        {"shape": "shell", "at": [16,0,-22],  "size": [6,22,6], "mat": "granite"} ] },
    { "name": "gate",   "parts": [
        {"shape": "arch", "at": [-5,0,-20], "span": 10, "rise": 6, "mat": "marble"} ] },
    { "name": "detail", "parts": [
        {"op": "box", "at": [-22,22,-22], "size": [6,1,6], "mat": "copper"} ] }
  ]
}
```

Shape keys are the generator's own parameters — the same names as the flags, with `-` or `_` both accepted. Get one wrong and `build.py` tells you which keys that generator does accept.

### 4. Build

```bash
build.py --dry-run < builds/castle.json    # validate every stage, send nothing
build.py < builds/castle.json              # land it, stage by stage
```

```
stage 1/5  ground      1 cmd    world cleared    350ms
stage 2/5  mass        6 parts  ids 1..6         440ms
stage 3/5  towers     12 parts  ids 7..18        548ms
```

**Every stage is bounds-checked and validated by the CLI before the first block is sent.** That is the reason to use a plan rather than five separate submissions: a misspelled material in the last stage would otherwise surface only after the first four had landed, and there is no partial undo — `remove` needs ids, so the only recovery is `clear` and start over.

Pacing defaults to the real settle time, so each stage finishes falling before the next begins. `--pace none` builds as fast as the server accepts; `--pace 800` holds a fixed beat.

`build.py` also marks the build so the viewer can tell your new parts from whatever was already in the world, and points its camera at yours — even if the reviewer had grabbed the camera to inspect something else. Without that mark the viewer would frame *everything ever built*, which with two structures far apart is two specks. Pass `--no-focus` when you deliberately want the camera left alone.

If a stage does fail part-way, the error names what already landed and its ids, and you resume with `--from N` once the plan is fixed. `--only NAME` re-sends a single stage — useful when iterating on the detail pass against an otherwise-finished build.

### 5. The generators

The four shape generators are usable from a plan (as `"shape": "..."`) or straight from the command line:

```bash
shapes.py bridge  --at 0,0,0 --span 40 --width 6 --deck-height 8 \
                  --mat oak --pier-mat granite --rail-mat oak_dark
shapes.py shell   --at 0,0,0 --size 20,12,16 --thickness 1 --mat brick
shapes.py stairs  --at 0,0,0 --steps 8 --rise 1 --run 2 --width 3 --mat slate --solid
shapes.py arch    --at 0,0,0 --span 16 --rise 6 --mat marble
```

Each writes NDJSON to stdout. Negative coordinates work bare (`--at -20,0,-3`);
no `=` needed.

For anything the generators do not cover, write the commands yourself — as raw `{"op": ...}` entries in a plan, or as NDJSON piped to `submit.py`. You are not restricted to these four shapes.

```bash
shapes.py bridge --span 40 --mat oak | submit.py
shapes.py bridge --span 40 --mat oak | submit.py --dry-run   # validate only
```

`submit.py` sends one batch and reports `addedIds`. It gates bounds itself, then asks the CLI to validate types and materials. Note that `codeblox exec --dry-run` on its own is **not** a full check — the published schema types fields and says nothing about geometry, so bounds are only evaluated once a batch is actually sent. Use `submit.py`, or `build.py` for anything with more than one stage.

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
larger part before a loop. This is per *stage*, not per build: few large parts each, several stages.

**Choose materials by family, then by name.** Structure reads better when the
family carries meaning — `metal` for supports, `glass` where light should pass,
`emissive` sparingly, as accents. A build using one material everywhere reads as
untextured.

**Give a structure proportion.** A bridge with a deck at 8 blocks and a 40-block
span reads right; the same deck at 40 blocks reads as a tower. When the prompt
does not specify, pick proportions that make the thing recognisable, and say what
you picked.

**Compose, and order the composition.** A castle is `shell` walls, `stairs` to the rampart, and `arch` for the gate — but *which lands first* is a design decision as much as the materials are. Write the pieces into a plan as stages, largest first, and let `build.py` land them in that order.

## Guardrails

- **Only material and op names `world.py` reports.** Anything else is refused
  before it is sent (exit 5).
- **Stay inside the bounds `world.py` reports.** `submit.py` gates this, but the
  gate is a safety net, not a design tool — plan inside the world.
- **Bounds are enforced by the server, not the schema.** The published contract
  types fields; it does not describe geometry. So a shape can be perfectly valid
  and still be refused for where it is (exit 6).
- **There is no carving.** `remove` takes an id, not a region, and parts are not
  voxels — nothing subtracts. Make openings by composing parts around the gap.
- **There is no partial undo.** Because `remove` needs ids, a build that stops
  half-way can only be unwound with `clear`. This is why `build.py` validates
  every stage before sending the first one — let it.
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

A `build.py` failure is either *before* anything was sent — the usual case, since the whole plan is gated up front — or part-way through, in which case the message says which stages landed and their ids. Read that line before deciding what to do: it is the difference between "fix the plan and re-run" and "the world is half-built, resume with `--from N`".
