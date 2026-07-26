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
world.py             what can I build with?         materials, ops, bounds, scale
dims.py to-blocks    how big is it, really?         millimetres -> blocks
   ↓ you decide what to build, at what size, and in what order it lands
plan.json            subject + stages, big to small  you write this
   | build.py        gate scale + bounds, then land  progress per stage
   ↑ dims.py fit     came out the wrong size?        rescales the plan

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

`world.py` also reports **`blocksPerMetre`**, derived from the contract. Read it; do not assume it. A block is not a metre, and it is not a fixed size either — it comes from `config.yaml` and can change.

### 3. Declare what you are building, at its real size

A plan carries a `subject`: the real-world size of the thing, in millimetres, as `x, y, z`.

```json
"subject": { "mm": [6000, 3500, 6000] }
```

This is not documentation. `build.py` measures the plan's own geometry against it and **refuses to send anything** if the two disagree, because there is no partial undo — a build discovered to be four times too small after it has landed can only be cleared and started over.

You do not do the conversion. `dims.py` does:

```bash
dims.py to-blocks 6000 3500 6000          # millimetres -> whole blocks, in x,y,z
dims.py to-blocks 4970 1964 1445 --lwh    # a spec sheet prints length,width,height
dims.py anchors                           # a person, a door, a storey, a lane, a step
```

`--lwh` exists because transposing length and height is the easiest way to declare a subject wrongly, and it fails quietly — every number stays plausible. `anchors` is for sizing something you have no figure for: a storey is 3 m, a door 2.03 m, so a six-storey building is 18 m without looking anything up.

If a build comes out the wrong size, do not rewrite it by hand:

```bash
dims.py fit < builds/thing.json > builds/thing.fixed.json
```

`fit` rescales every part about the build's grounded centre. It refuses when the axes are wrong by *different* factors, because that is a proportion error and one factor cannot repair three ratios — scaling anyway would give you a correctly-sized wrong shape, which is worse, since it then passes the gate.

### 4. Plan the stages

**Build order is not bookkeeping — it is what the audience watches.** The viewer drops every newly added part in from six blocks up, staggered a few milliseconds apart, and a part that has settled never moves again. So each batch you submit is *one animation beat*. A structure sent as one flat batch lands as one undifferentiated shower; the same structure sent as five stages reads as something being built.

Work bottom-up, big to small:

| # | Stage | What lands |
|---|---|---|
| 1 | **Ground** | `world.py` to see the world, then a `clear` if you are replacing what is there |
| 2 | **Mass** | the big forms — the silhouette, in the fewest parts that carry it |
| 3 | **Structure** | towers, limbs, spans — what grows out of the mass |
| 4 | **Openings** | doors, windows, arches |
| 5 | **Detail** | finials, eyes, teeth, accents in a contrasting family |

**Openings are composed, not carved.** There is no boolean subtraction in this engine — geometry is scaled parts, and `remove` deletes a part *by id*, not a region. You cannot punch a hole in a wall. A wall with a window is the sill, the head and the two jambs, and the opening is simply what was never built. You do not work those four rectangles out: `shapes.py window` does, and fills the gap with glazing if you name a material. Same for a door — its sill is the floor, so that piece is omitted rather than emitted at zero height.

**Nothing is ever rotated.** Every part is axis-aligned; the renderer composes each instance with an identity rotation. So a raked surface — a windshield, a backlight, a skylight, a canopy — is a *staircase of thin slabs*, not a tilted box. `shapes.py pane` computes that stack, and its `--steps` is the dial between smoothness and part count. Hand-stepping a rake is how one car's greenhouse came to be 178 of its 305 parts.

A plan is one JSON object, and it is worth keeping — the whole build is reproducible from it, and re-running one stage beats rebuilding from scratch. Write it to `builds/<name>.json` rather than leaving it loose in the project root. That directory is the working space for plans and is not tracked, so treat it as yours to fill. Each part is either a **shape call** (expanded through the generators below) or a **raw command** passed through untouched:

```json
{
  "name": "pavilion",
  "subject": { "mm": [6000, 5000, 6000] },
  "stages": [
    { "name": "ground", "parts": [ {"op": "clear"} ] },
    { "name": "floor",  "parts": [
        {"op": "box", "at": [-150,0,-150], "size": [300,10,300], "mat": "slate"} ] },
    { "name": "walls",  "parts": [
        {"shape": "window", "at": [-150,10,140], "size": [300,140,10], "hole": [80,0,140,110],
         "mat": "brick", "glass-mat": "glass"},
        {"shape": "window", "at": [-150,10,-140], "size": [10,140,280], "hole": [40,40,200,70],
         "mat": "brick", "axis": "z", "glass-mat": "glass_azure"} ] },
    { "name": "roof",   "parts": [
        {"shape": "dome", "at": [0,150,0], "size": [300,60,300], "mat": "copper"} ] },
    { "name": "finial", "parts": [
        {"shape": "taper", "at": [-15,210,-15], "size": [30,40,30], "top": [4,4], "mat": "gold"} ] }
  ]
}
```

Note the magnitudes: a 6 m pavilion is 300 blocks across, not 6 and not 40. That is what declaring `subject.mm` is for — you write the real size once and the gate holds the geometry to it.

Shape keys are the generator's own parameters — the same names as the flags, with `-` or `_` both accepted. Get one wrong and `build.py` tells you which keys that generator does accept.

### 5. Build

```bash
build.py --dry-run < builds/pavilion.json    # validate every stage, send nothing
build.py < builds/pavilion.json              # land it, stage by stage
```

```
stage 1/5  ground       1 cmd    world cleared                       350ms
stage 2/5  floor        1 cmd    ids [1]         6×0.2×6 m           350ms
stage 3/5  walls       19 parts  ids 2..20       6×2.8×6 m           674ms
stage 4/5  roof         1 cmd    ids [21]        6×2.4×6 m           350ms
```

Each line reports what the stage landed **in metres**, which is the only unit you can sanity-check by eye. A stage that reads `0.2×6 m` when you meant a 6 m floor slab tells you the mistake before the gate has to.

**Every stage is bounds-checked and validated by the CLI before the first block is sent.** That is the reason to use a plan rather than five separate submissions: a misspelled material in the last stage would otherwise surface only after the first four had landed, and there is no partial undo — `remove` needs ids, so the only recovery is `clear` and start over.

Pacing defaults to the real settle time, so each stage finishes falling before the next begins. `--pace none` builds as fast as the server accepts; `--pace 800` holds a fixed beat.

`build.py` also marks the build so the viewer can tell your new parts from whatever was already in the world, and points its camera at yours — even if the reviewer had grabbed the camera to inspect something else. Without that mark the viewer would frame *everything ever built*, which with two structures far apart is two specks. Pass `--no-focus` when you deliberately want the camera left alone.

If a stage does fail part-way, the error names what already landed and its ids, and you resume with `--from N` once the plan is fixed. `--only NAME` re-sends a single stage — useful when iterating on the detail pass against an otherwise-finished build.

### 6. The generators

Nine generators, usable from a plan (as `"shape": "..."`) or straight from the command line. Every one of them exists because its arithmetic is where a model reliably slips — segment placement, stepped rakes, the four rectangles around an opening — and none of it is a judgment call.

```bash
# enclosures and structure
shapes.py shell   --at -150,0,-150 --size 300,150,300 --thickness 10 --mat brick
shapes.py stairs  --at 0,0,0 --steps 15 --rise 10 --run 15 --width 60 --mat slate --solid
shapes.py arch    --at 0,0,0 --span 200 --rise 100 --mat marble
shapes.py bridge  --at 0,0,0 --span 2000 --width 300 --deck-height 400 \
                  --mat oak --pier-mat granite --rail-mat oak_dark
shapes.py taper   --at -60,0,-60 --size 120,400,120 --top 20,20 --steps 10 --mat granite

# rounded forms, on the native ops
shapes.py wheel   --at 0,35,-120 --r 35 --width 20 --axis x --mat slate_dark --hub-mat silver
shapes.py dome    --at 0,150,0 --size 300,60,300 --mat copper

# glazing
shapes.py window  --at -150,0,140 --size 300,140,10 --hole 80,0,140,110 \
                  --mat brick --glass-mat glass
shapes.py pane    --at -55,60,-100 --width 110 --run 90 --rise 40 --steps 20 \
                  --thickness 4 --mat glass_azure --frame-mat slate_dark --frame 6
```

`--steps` is worth setting deliberately. It defaults to one slab per block of rise — as smooth as the grid allows, and the most parts. Halving it halves the parts and the stepping is usually still invisible at a block's scale.

| generator | what it is for |
|---|---|
| `shell` | a hollow box — floor, roof, four walls, inset so faces meet |
| `stairs` | a flight of steps along x or z; `--solid` fills each to the base |
| `arch` | a semi-elliptical arch, approximated in `--segments` boxes |
| `bridge` | deck, piers, optional railings |
| `taper` | slabs narrowing from a base footprint to a top — spires, hulls, chimneys |
| `wheel` | a `tube` about x, y or z, with an optional proud hub |
| `dome` | an `ellipsoid` of twice the rise, half of it inside what it sits on |
| `window` | a wall composed around an opening, optionally glazed |
| `pane` | raked glazing as a stack of thin slabs, framed on all four sides |

Each writes NDJSON to stdout. Negative coordinates work bare (`--at -20,0,-3`);
no `=` needed.

For anything the generators do not cover, write the commands yourself — as raw `{"op": ...}` entries in a plan, or as NDJSON piped to `submit.py`. You are not restricted to these nine shapes.

```bash
shapes.py bridge --span 40 --mat oak | submit.py
shapes.py bridge --span 40 --mat oak | submit.py --dry-run   # validate only
```

`submit.py` sends one batch and reports `addedIds`. It gates bounds itself, then asks the CLI to validate types and materials. Note that `codeblox exec --dry-run` on its own is **not** a full check — the published schema types fields and says nothing about geometry, so bounds are only evaluated once a batch is actually sent. Use `submit.py`, or `build.py` for anything with more than one stage.

## Coordinates

Coordinates are in **blocks**, and a block is not a metre — `world.py` reports
`blocksPerMetre` and `dims.py to-blocks` does the conversion. `world.py` also
reports the buildable range; note that **y starts at 0** — the floor — while x
and z are symmetric about the origin. Nothing may be built below y=0.

Anchoring differs per op, and `shapes.py` already handles it. You only need this
when hand-writing commands:

| op | `at` means |
|---|---|
| `box` | the **minimum corner** — the box grows toward +x, +y, +z |
| `fill` | `from`/`to` are **inclusive cells**, so the extent is \|to-from\|+1 |
| `sphere` | the **centre** |
| `ellipsoid` | the **centre**, and `size` is the **full** extent, not a radius |
| `cylinder` | the **centre**, and the height is centred on it too |
| `tube` | the **centre**; `h` runs along `axis`, the other two axes take the diameter |

That `cylinder` row is the easy mistake: a `box` at y=10 sits *on* y=10, but a
`cylinder` at y=10 with height 8 spans y=6 to y=14.

**Nothing is ever rotated.** Every part is axis-aligned — which is why `tube`
carries a named `axis` rather than an orientation, and why anything raked has to
be stepped.

## Judgment — what is actually yours

**Spend parts on what is visible, not on a part budget.** The renderer keeps one instanced mesh per *(geometry kind × render family)* and colours each instance individually. There are five geometry kinds and four families, so **the whole world is at most twenty draw calls no matter how many parts you build** — forty boxes of forty different opaque materials are one draw call, not forty. Part count costs an instance slot and a matrix, and every instance is submitted each frame whether it is on screen or not, so cost tracks the total, not the visible subset. There is no protocol ceiling either.

What that means in practice: do not contort a design to save parts. Do not spend three hundred parts on interior detail nobody will see, or on stepping a curve finer than a block. A rough budget by subject, for legibility rather than for the engine — a vehicle or a creature reads well at 50–300 parts, a building at 100–500, a landmark at 300–1000. Past that you are usually adding detail below the size of a block, which cannot render.

**Choose materials by family, then by name.** Structure reads better when the
family carries meaning — `metal` for supports, `glass` where light should pass,
`emissive` sparingly, as accents. A build using one material everywhere reads as
untextured.

**Get the proportions from the real thing, not from the block grid.** You know
what a car, a bear, a storey, a suspension bridge actually measure — that
knowledge is the most valuable thing you bring, and `subject.mm` is where it goes.
When the prompt does not specify, pick real dimensions, say what you picked, and
let `dims.py` turn them into coordinates. Reach for `dims.py anchors` when you
have no figure at all.

**Compose, and order the composition.** A pavilion is `window` walls, a `dome` roof and a `taper` finial; a car is a `taper` hull, `pane` glazing and four `wheel`s — but *which lands first* is a design decision as much as the materials are. Write the pieces into a plan as stages, largest first, and let `build.py` land them in that order.

## Guardrails

- **Only material and op names `world.py` reports.** Anything else is refused
  before it is sent (exit 5).
- **Stay inside the bounds `world.py` reports.** `submit.py` gates this, but the
  gate is a safety net, not a design tool — plan inside the world.
- **Bounds are enforced by the server, not the schema.** The published contract
  types fields; it does not describe geometry. So a shape can be perfectly valid
  and still be refused for where it is (exit 6).
- **There is no carving.** `remove` takes an id, not a region, and parts are not
  voxels — nothing subtracts. Make openings by composing parts around the gap;
  `window` does it for a wall, and `shell` already does it internally.
- **Declare `subject.mm` and let the gate hold you to it.** A build that does not
  match its declaration is refused before anything is sent (exit 5), with the
  per-axis ratio and either `dims.py fit` or a note that the proportions are
  wrong. Do not delete the declaration to make the gate quiet.
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
