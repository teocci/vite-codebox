# vite-codebox

A Vite-powered vanilla JavaScript sandbox — a lightweight starting point for building modular, framework-free web components with modern tooling.

## Features

- Vite dev server with instant HMR and optimized production builds
- Vanilla ES6+ JavaScript — no frameworks, no black boxes
- CSS Modules with CSS custom properties for design tokens
- Component-based structure with clear separation of concerns

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
npm run dev
```

Open the URL printed in the terminal (default `http://localhost:5173`).

### Build

```bash
npm run build
```

Output is emitted to the `dist/` directory.

### Preview

```bash
npm run preview
```

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
├── scripts/gen-config.mjs    # config.yaml -> packages/shared/config.values.js
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
