# The bug that only an agent could hit

For two releases, this command reported success and did nothing:

```console
$ codeblox clear --r 5 --id 9
$ echo $?
0
```

`clear` wipes the world. It takes no radius and no id. Those two flags were
accepted, ignored, and discarded — and the command exited `0`, the universal
signal for *it worked*.

Nobody noticed. Not because the code was unread, but because of who was reading
the output. A person who runs that command looks at the screen, sees a world that
did not change, shrugs, and retypes it. The exit code is not how they find out
what happened — their eyes are. The wrong exit code costs them nothing.

An agent has no eyes. It reads `0`, records *world cleared*, and plans its next
step on top of a fact that is not true.

That is the whole argument, and everything below is elaboration: **when the
primary consumer of your software stops being a person, the failure modes change
shape.** Not the failure *rate* — the failure *shape*. Bugs that were invisible
become fatal, and bugs that were fatal become trivial.

---

## The setup

**codeblox** is a block-building engine — think a very small Roblox. There is a
browser viewer, an authoritative WebSocket server that owns the world, and a
command-line client.

The unusual part is the operating model: **the agent builds, the human reviews.**
The CLI was not written for a person who occasionally scripts it. It was written
for a model that drives it constantly, through wrapper scripts, and a person who
looks at the result and says yes or no.

That inversion is the only premise. Everything that follows was forced by it.

It is worth saying plainly what this is and is not evidence of. This is a small
project. The world is blocks. The "agent" is a coding assistant operating a CLI,
not an autonomous system with goals of its own. What makes it useful as evidence
is not scale — it is that the premise was taken seriously enough to follow all
the way down, and the consequences turned out to be specific and surprising.

---

## Four things that changed

### 1. Silent success is the new crash

The `clear` bug was not alone. The same root cause — one shared flag definition
serving every command — produced a family:

```console
$ codeblox exec batch.json --json      # --json is silently discarded
1 command valid against the server contract; nothing sent
$ echo $?
0
```

That one is worse than it looks. The command-line parser stops at the first
argument that is not a flag, so `--json` after `batch.json` was never seen. The
tool printed an English sentence to standard output and exited `0`. The wrapper
script, told it had asked for JSON, called `json.loads` on *"1 command valid
against the server contract"* — and crashed.

The agent then sees a Python traceback. It concludes the *wrapper* is broken. It
starts debugging the wrong layer, confidently, because nothing in what it
received points at the real cause.

This is the characteristic agent-era failure: not an error, but a **confident
wrong answer that misdirects the diagnosis**. A human debugging the same thing
would have glanced at the output, seen prose where JSON should be, and known
within seconds.

The fix was unglamorous — every command declares only the flags it actually
reads, and rejects the rest — but the discipline it implies is not. **Accepting
input you intend to ignore is now a defect.**

### 2. Exit codes are an API, not a formality

Every failure in the CLI used to exit `1`. That is normal. It is also useless.

The wrapper needs to decide what to do next, and the choices are genuinely
different:

| What went wrong | What the caller must do |
|---|---|
| No credential | re-authenticate |
| Server unreachable | retry, with backoff |
| Material not in the palette | re-plan the build |
| Rejected before sending | fix and retry safely — nothing happened |
| Rejected by the server | something may have happened; check |

Behind a single `1`, the only way to tell those apart is to pattern-match English
error text — which changes whenever someone improves the wording. You end up with
a wrapper coupled to your prose.

So the exit codes became a published contract: `2` usage, `3` auth, `4` network,
`5` rejected here, `6` rejected by the server. Under `--json`, failures emit a
single-line envelope on standard error:

```json
{"ok":false,"code":"not_authenticated","exit":3,"detail":"not authenticated — run `codeblox auth login`"}
```

The distinction between `5` and `6` is the one that earns its keep. `5` means the
batch was rejected locally and **nothing was sent** — retry is free. `6` means it
reached the server and was refused — the world may have partially changed. A
human reads both as "it didn't work." An agent has to act differently.

There is a general principle here that predates agents but was easy to skip:
**anything a caller must branch on has to be structured.** We were always
supposed to do this. Human tolerance for prose let us not.

### 3. The tool publishes its own capabilities

The client compiles in no list of commands and no list of materials. Both arrive
from the server at runtime, as a published contract:

```console
$ world.py
block 2 cm (0.02 m)   world 32 m half-extent
bounds  x -1600..1600   y 0..3200   z -1600..1600  (blocks)
ops     box, clear, cylinder, fill, remove, sphere, world_info
materials 100 in 4 families:
  emissive    9  arcane, ember, flame, lantern  …
  glass       8  crystal, glass, glass_amber, moonstone  …
  metal      13  brass, bronze, copper, gold, iron  …
  opaque     70  amethyst, basalt, brick, cedar  …
```

Add a material to the server and every client can use it immediately. No release,
no version negotiation, no table to update in three places.

This matters more with a model than with a person. A person reads the docs once
and remembers. A model rebuilds its understanding on every invocation — so the
cheapest correct thing is to hand it the current truth each time, rather than
hope the documentation and the server have not drifted apart.

The corollary is sharper than it sounds: **documentation that can drift from the
system is a liability, and the fix is to stop writing it.** The 100 material
names appear nowhere in the skill's instructions. They cannot go stale, because
they are not written down.

### 4. Push determinism down; leave judgment up

The skill that drives all this could have been a document: here are the commands,
here is the coordinate system, here are some examples, good luck.

That document would be re-interpreted probabilistically on every run. Instead,
every mechanical step became a tested script, and the written instructions kept
only what genuinely needs judgment.

Building a bridge is a good illustration. The model decides the span, the height,
the materials, whether it has railings — the design. It computes none of the
coordinates:

```console
$ shapes.py bridge --span 40 --width 6 --deck-height 8 \
            --mat oak --pier-mat granite --rail-mat oak_dark
{"op":"box","at":[0,8,0],"size":[40,1,6],"mat":"oak"}
{"op":"box","at":[12,0,1],"size":[3,8,4],"mat":"granite"}
{"op":"box","at":[25,0,1],"size":[3,8,4],"mat":"granite"}
{"op":"box","at":[0,9,0],"size":[40,1,1],"mat":"oak_dark"}
{"op":"box","at":[0,9,5],"size":[40,1,1],"mat":"oak_dark"}
```

Pier spacing, deck offsets, rail placement — arithmetic, and arithmetic across
dozens of parts is exactly where a language model quietly drops one or shifts a
row by one block. It is also not a judgment call. There is one right answer, so
it belongs in code.

The test for whether something belongs in a script is simple: **what
probabilistic failure does putting it here remove?** If the answer is "none," it
stays prose. That test kept the script count honest — and it is the reason the
instructions are short. Everything a script could own, a script owns.

Nine words in that skill's guidance carry more weight than any of the mechanics:
*prefer few large parts over many small ones.* One 40×1×6 deck is one object in
the engine; forty 1×1×6 blocks are forty. They look identical and one costs forty
times as much. That is taste, and taste is what the model is for.

---

## The decision that inverted

Partway through, the command-line parsing needed rebuilding. In Go, the reflexive
answer is Cobra — it is what kubectl, gh, docker, and hugo use, and it is a good
library.

Three independent evaluations were run against different rubrics: fit with the
existing code, correctness for a machine consumer, and dependency weight. **All
three ranked the standard library first.** Not narrowly — there was no weighting
of the three under which a framework won.

The reasoning is worth repeating because it generalises. A CLI framework's value
is concentrated in things this consumer cannot use:

- **Shell completion** — nothing is typing.
- **Generated help pages** — nothing is reading them.
- **Man pages** — same.

Meanwhile the things that *do* matter — rejecting unknown flags, stable error
text, predictable exit codes — are either not what the framework sells you, or
are things you end up hand-writing anyway.

Two specifics sealed it. Cobra's module declares an old Go version, which
disables dependency-graph pruning, so depending on it drags seven modules into
the build — including a Markdown renderer — for two that actually link. And on
Windows it links a library that detects launch-from-Explorer, prints help, and
then **blocks waiting for a keypress**. On the target platform. For a caller that
cannot press a key.

There was also a fashionable option: a library that wraps Cobra with styled,
coloured help and errors. It was rejected in one line — it writes ANSI escape
codes into the stream the wrapper parses. It degrades correctly when output is
not a terminal *usually*, and "usually" is not a property you want gating an
agent's control flow.

**Best practice is consumer-relative.** Cobra remains the right answer for a tool
humans type. It was the wrong answer here, and the only thing that changed was
who calls it.

---

## The thing that cannot be published

One detail resisted every principle above, and it is the interesting one.

The server publishes what each command's fields *are* — that `at` is three
integers, that `mat` is a material name. It does not publish what they *mean*.
And the meaning is not uniform:

| Command | What `at` refers to |
|---|---|
| `box` | the **minimum corner** — it grows toward +x, +y, +z |
| `sphere` | the **centre** |
| `cylinder` | the **centre**, and its height is centred on that too |

A box at height 10 sits *on* 10. A cylinder at height 10, eight blocks tall,
spans 6 to 14. Get that wrong and parts land half a structure away — and the
server accepts them, because they are perfectly valid geometry. Just not what
anyone meant.

This is the one rule the tooling has to know locally, so it is the one rule that
can silently drift out of agreement with the server. The response was a test that
checks it **behaviourally** rather than by reading the code: place a shape so its
computed extent rests exactly on the floor — it must be accepted. Place the same
shape one block lower — it must be refused. If the server ever changes how it
derives a part's extent, one of those two flips and the build fails loudly.

The general shape of this: **you cannot eliminate every assumption, so find the
ones you cannot eliminate and pin them from the outside.** Not "is the constant
still correct" — "does the system still behave as though it were."

---

## What this suggests about where things go

Nothing here required new technology. Every fix is decades-old practice —
validate your input, use meaningful exit codes, emit structured output, test at
the boundary. The reason they went undone is that human tolerance made them
optional. A person compensates for a sloppy interface without noticing they are
doing it, hundreds of times a day.

Take the person out and the compensation goes with them.

So the prediction is not that AI will write our software. It is narrower and, I
think, more useful:

**Agents are about to become the most demanding users your interfaces have ever
had — and their bug reports are the ones you have been ignoring.** Every silent
no-op, every overloaded exit code, every error message that only makes sense to
someone who already knows the codebase — these were always defects. They were
just defects nobody filed.

The second-order effect is the one worth watching. Once the mechanical work is
genuinely in scripts, what is left for the model is design, proportion, taste,
and judgment about tradeoffs. That is not a diminished role. It is the part that
was always the job — the rest was overhead we had accepted because the tools
demanded it.

And a note on provenance, since it is on-topic: most of this codebase was written
by an agent, with a human reviewing and pushing back. The framework evaluation
above happened because the reviewer asked a blunt question — *why are you not
using the standard library for this?* — and the answer turned out to be
"reflex, not reasoning." That exchange is the model in miniature. The agent
covered ground quickly and got the defaults wrong; the human asked the question
that reframed it. Neither half is optional yet.

---

## If you want to poke at it

```bash
npm install && npm start        # viewer on :5173, world server on :7799

# then, from the skill:
doctor.py                       # is everything actually working?
world.py                        # what can I build with?
shapes.py bridge --span 40 --mat oak | submit.py
```

The bugs described above are all in the git history, along with the fixes and the
reasoning. `docs/improvements/` records why each decision went the way it did,
including the ones that were reversed.
