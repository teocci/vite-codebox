import { defineConfig } from 'vite'
import { WEB } from '@codeblox/shared/config.js'

// The viewer lives in apps/web — a sibling of apps/server, so neither app is
// nested inside the other. Vite's root is that app; the build still lands in the
// repo-level dist/ so there is one output directory for the whole workspace.
//
// Shared modules are imported by workspace package name (@codeblox/shared/*),
// which resolves identically for Vite, Node, and vitest — no aliases, and no
// ../../../ chains reaching across app boundaries.
export default defineConfig({
  root: 'apps/web',
  server: { host: WEB.host, port: WEB.port, strictPort: true },
  preview: { host: WEB.host, port: WEB.port, strictPort: true },
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
  },
  test: {
    root: '.',
    environment: 'node',
    include: ['tests/**/*.test.js'],
  },
})
