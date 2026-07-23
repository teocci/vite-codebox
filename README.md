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

```
vite-codebox/
├── src/
│   ├── components/   # Reusable UI components (.js + .module.css)
│   ├── services/     # Shared services (api, i18n)
│   ├── styles/       # Global CSS and design tokens
│   └── main.js       # Application entry point
├── index.html
└── vite.config.js
```

## License

[MIT](LICENSE) © Teocci
