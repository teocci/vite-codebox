# Phase 17 — codeblox view — presentation gets its own verb group

- **Phase ID:** 17
- **Version:** (pending)
- **Date:** (pending)
- **Tests:** (pending)
- **Status:** 🚧 IN PROGRESS

## Objective

Give presentation its own verb group rather than routing it through `exec`, the batch runner —
`codeblox view <1-6> | reframe | rotate on|off | grid on|off | hud on|off`, mirroring `auth`. Add a
real `bool` field type to the contract so a bad flag is refused before anything is sent, instead of
landing every part in the batch and silently skipping the directive. Carries I-14.

## What was built

**A `view` verb group**, in a new `dispatch_view.go` following `dispatchAuth`/`dispatchBuild`:
`codeblox view N`, `view reframe`, and `view rotate|grid|hud on|off`. It reuses `flagSurface`, the
common flags, `--dry-run`, `--json` and the existing session path, and rejects unknown subcommands
and stray arguments the way I-1 established.

The group exists because presentation is not a build verb. `exec` is the batch runner — it parses a
JSON array, object or NDJSON from stdin and validates the whole batch before sending — and routing
camera and HUD direction through it is a category error. The CLI already draws this line: `clear` is
an op *and* a verb, as are `box`, `sphere`, `cylinder` and `remove`.

**A real `bool` field type in `contract.go`.** This is deliberately not the `axis` deferral, and the
line between them is the value domain: `axis` means `x|y|z`, which is server data the package refuses
to compile in, while `bool` is a structural JSON check fully described by its type name — the same
category as `int+` and `id`, both already implemented. It matters because of *how the server fails*.
`applyBatch` records a rejected command and continues, so a batch of thirty parts ending in
`{"op":"rotate","on":"yes"}` would land all thirty and silently not rotate, with the reason buried in
an ack the CLI drops. Client-side rejection kills the batch before anything is sent.

`view.n` stays `int+` on the Go side. A `view` type would compile in "there are six presets" —
precisely the server knowledge this package exists not to hold — so an out-of-range preset is
forwarded and refused by the server, and a test pins that so nobody later "fixes" it by hardcoding
the count. Carries I-14.

## Files changed

| File | Change |
|---|---|
| `clients/codeblox/internal/command/dispatch_view.go` | New — the group |
| `clients/codeblox/internal/command/dispatch.go` | Routing arm + `presentation:` usage block |
| `clients/codeblox/internal/contract/contract.go` | `typeBool` + its `checkField` case |
| `clients/codeblox/internal/command/dispatch_view_test.go` | New — 12 test functions |
| `clients/codeblox/internal/contract/contract_test.go` | 3 new tests; sample contract widened |

## Verification

`npm run test:cli` → 127 test functions (15 new), run with `-count=1`. `npm run test:e2e` → 24, green
against the live server. `go vet` clean. Driven end-to-end with the built binary: `view 1` and
`view rotate off` succeed, `view 99` exits **6** (the server refuses it, not the client),
`view grid yes` and `view zoom` exit 2 with nothing sent, and a batch ending in `on:"yes"` exits 5
with the box in front of it never landing. See I-14's Verification for the transcripts.
