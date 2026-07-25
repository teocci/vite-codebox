/**
 * Engine units and world config — the single source of truth for VALUES.
 *
 * The values come from config.yaml, compiled to ./config.values.js by
 * scripts/gen-config.mjs (run on install / predev / prebuild / pretest). Both the
 * browser viewer and the Node server import the same module — no environment
 * variables, no .env, just file-based config that works on any host.
 *
 * BLOCK_SIZE is metres per block: the resolution quantum. Engine math runs in
 * block space (integer block coordinates); BLOCK_SIZE is applied exactly once, at
 * the render/display boundary. World size is measured in METRES, independent of
 * BLOCK_SIZE, so the block can be tiny without shrinking the world. A literal
 * metre value anywhere else in the codebase is a bug — use metres() / blockLabel().
 */

import values from './config.values.js'

export const BLOCK_SIZE = values.blockSize

/** Convert a length in blocks to metres. */
export const metres = blocks => blocks * BLOCK_SIZE

/** Convert a length in metres to (fractional) blocks. */
export const blocks = m => m / BLOCK_SIZE

/** Human-readable label for one block, e.g. "1 m" or "2 cm". Float-safe. */
export const blockLabel = () =>
  BLOCK_SIZE >= 1 ? `${+BLOCK_SIZE.toFixed(3)} m` : `${+(BLOCK_SIZE * 100).toFixed(2)} cm`

/**
 * World bounds. extent and gridStep are in METRES (independent of BLOCK_SIZE);
 * the *Blocks getters convert to the integer block limits used for build bounds.
 */
export const WORLD = {
  extent: values.extent,
  gridStep: values.gridStep,
  /** Max |x| and |z| in blocks. */
  get boundBlocks() {
    return Math.round(this.extent / BLOCK_SIZE)
  },
  /** Max y in blocks (buildable height = 2×extent metres). */
  get heightBlocks() {
    return Math.round((this.extent * 2) / BLOCK_SIZE)
  },
}

/** Viewer server — Vite dev/preview (serves the browser app). */
export const WEB = {
  host: values.web.host,
  port: values.web.port,
}

/** Authoritative WebSocket command server binding. */
export const WS = {
  host: values.ws.host,
  port: values.ws.port,
  seed: values.ws.seed,
  authRequired: values.ws.authRequired,
}
