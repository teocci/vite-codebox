# codeblox

A block-building engine on Three.js whose primary operator is an **AI agent**. The agent builds; the
human reviews.

A browser viewer renders the world, an authoritative WebSocket server owns it, and a Go CLI is the
agent's hands. The client compiles in no list of commands and no list of materials — both are
published by the server at runtime, so a new material needs no client release.

> **Why this repo is interesting beyond the blocks:** taking "the operator is a model, not a person"
> seriously changes what a good interface is. Silent success becomes the worst failure mode, exit
> codes become an API, and the reflexive best practice turns out to be wrong. The story of what
> broke and why is in **[The bug that only an agent could hit](docs/agent-driven-development.md)**.

## Features

- Agent-operated: a documented CLI contract — structured errors, meaningful exit codes, and a
  runtime-published capability schema — designed for a caller that cannot read prose
- O(1) part add/remove via `InstancedMesh` swap-remove, one draw call per geometry × render family
- Vanilla ES6+ JavaScript — no frameworks, no black boxes
- One dial for scale: `config.yaml` compiles to shared config; no literal metre appears anywhere else

## Getting Started

### Prerequisites

- Node.js 18+
- npm (or pnpm / yarn)

### Installation

```bash
git clone https://github.com/teocci/vite-codebox.git
cd vite-codebox
npm install
```

### Development

```bash
npm start        # viewer on :5173 and the world server on :7799
```

Open `http://localhost:5173`. `npm run dev` starts the viewer alone, which falls back to applying
commands locally — useful for engine work, but nothing is shared and nothing persists.

To drive the world from an agent, build the CLI:

```bash
npm run build:cli                                   # -> clients/codeblox/bin/
```

### Authenticating the CLI

**The CLI always needs a stored credential — even though the default server does not check it.**
Those are two independent switches, and conflating them is the first thing that trips a fresh clone:

```bash
codeblox info
# {"ok":false,"code":"not_authenticated","exit":3,"detail":"not authenticated — run `codeblox auth login`"}
```

That failure appears even on a stock checkout, where `config.yaml` ships `ws.auth.required: false`
and the server accepts *any* token. The client refuses to dial before it has something to send;
the server is what decides whether the token matters.

The token is generated for you. On first `npm start` the server writes 24 random bytes to
`.codeblox/token` (mode `0600`, gitignored) unless `CODEBLOX_TOKEN` is set in the environment, which
wins. So the login step is to hand that file to the CLI:

```bash
# Git Bash / macOS / Linux
cat .codeblox/token | codeblox auth login --with-token

# PowerShell
Get-Content .codeblox\token | codeblox auth login --with-token
```

Then confirm it against a running server:

```bash
codeblox auth status
# connected to ws://127.0.0.1:7799
# token: 0ca2…fc50   source: keyring   backend: keyring
# server returned its world_info contract
# note: a server running with auth disabled accepts any token
```

That last line is not boilerplate — with `required: false` the connection proves the server is
reachable, **not** that your token is correct. To make the check meaningful, set
`ws.auth.required: true` in `config.yaml` and restart; a wrong token is then refused at the
handshake.

`auth login` with no `--with-token` prompts instead, with echo off. The secret goes to the OS
keyring, falling back to a `0600` file at `~/.codeblox/auth.json` on hosts with no keyring; it is
never written to the settings file and is masked everywhere it is printed. `codeblox auth list`
shows what is stored, `codeblox auth logout` removes it.

If the binary is not on your `PATH`, call it by path (`clients/codeblox/bin/codeblox.exe` on
Windows) or run `.venv/Scripts/python .claude/skills/codeblox-builder/scripts/install_codeblox.py`
to register it on the User `PATH`. Pass `--dry-run` first — it is the only step that changes
anything outside the repo.

Once `auth status` is green, the skill's preflight should pass:

```bash
.venv/Scripts/python .claude/skills/codeblox-builder/scripts/doctor.py
```

### Build

```bash
npm run build
```

Output is emitted to the `dist/` directory.

### Preview

```bash
npm run preview
```

### Stopping the dev servers

`npm start` runs the viewer and the ws server under `concurrently`. To stop them — and any stale
listener left over from an earlier session — use:

```bash
npm run dev:list    # show what holds the ports, kill nothing
npm run dev:stop    # force-stop them (tree kill, so concurrently goes too)
```

Ports come from `config.yaml`, never hardcoded. Extra ports can be added as positional arguments,
which is useful for an ad-hoc server: `npm run dev:stop -- 7801`.

> **npm eats flags.** This npm forwards only *positional* arguments after `--`; every `--flag` is
> stripped, verified by probe. `npm run dev:stop -- --list` would therefore kill everything while
> looking like a dry run — which is exactly why `dev:list` is its own script with the flag baked in.
> Flags behave normally when node runs the script directly:
> `node scripts/js/dev-stop.mjs --list --json 7801`.

A held lock is not hypothetical: a running Vite dev server keeps a handle on `apps/web/src`, and
`git mv` on it fails with `Permission denied` until the server is stopped.

## Project Structure

An npm-workspaces monorepo. The two servers are siblings — neither is nested inside the other.

```
vite-codebox/
├── apps/
│   ├── web/                  # Viewer (browser). Vite's root.
│   │   ├── index.html
│   │   └── src/
│   │       ├── engine/       # InstancedLayer, World, DropAnimator, geometry
│   │       ├── viewer/       # Viewer, CameraDirector, Grid, Hud
│   │       ├── net/          # WsClient
│   │       ├── styles/
│   │       └── main.js
│   └── server/               # Authoritative WebSocket server (Node)
├── packages/
│   └── shared/               # @codeblox/shared — dependency-free source of truth
│                             # config, materials, families, protocol
├── clients/
│   └── codeblox/             # Go CLI (the agent's hands); builds to bin/
├── scripts/
│   ├── js/                   # gen-config (config.yaml -> config.values.js), dev-stop
│   └── py/                   # mirror_skill — copies the skill to the other agent dot-dirs
├── tests/                    # vitest, covering apps/ and packages/
├── config.yaml               # the one place to change block size, world, ports
└── vite.config.js            # root: apps/web, build.outDir: ../../dist
```

Shared code is imported by workspace package name — `@codeblox/shared/protocol.js` — which
resolves identically under Vite, Node, and vitest. No aliases, and no `../../../` chains
crossing an app boundary.

`dist/` holds the browser build only. The Go CLI builds to `clients/codeblox/bin/`
(`npm run build:cli`); both are gitignored.

## License

[MIT](LICENSE) © Teocci
