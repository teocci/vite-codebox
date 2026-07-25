import { defineConfig } from 'vite'
import { WEB } from './shared/config.js'

// The viewer's host/port come from config.yaml (compiled to shared/config.values.js),
// so both servers are configured in one place. Shared modules are imported by
// relative path (no aliases) so the Node server can import them unchanged.
export default defineConfig({
  server: { host: WEB.host, port: WEB.port, strictPort: true },
  preview: { host: WEB.host, port: WEB.port, strictPort: true },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.js'],
  },
})
