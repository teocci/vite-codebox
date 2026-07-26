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

// A floor grid is a reading aid, so what matters is the cell COUNT, not the cell
// size: ~64 cells across stays legible whether the world is a room or a valley.
// Holding gridStep at a fixed 1 m is what turns a kilometre world into 2800
// unreadable divisions.
const GRID_TARGET_DIVISIONS = 64
const GRID_LADDER = [1, 2, 5]

/**
 * Grid cell size in metres for a world of this half-extent: the smallest
 * 1-2-5 ladder rung that gets the cell count at or under the target. The ladder
 * is what keeps the number itself round — a derived 43.75 m cell is legible to
 * nobody, 50 m is.
 */
export const gridStepFor = extentMetres => {
  const ideal = (extentMetres * 2) / GRID_TARGET_DIVISIONS
  const decade = 10 ** Math.floor(Math.log10(ideal))
  for (const rung of GRID_LADDER) {
    if (rung * decade >= ideal) return rung * decade
  }
  return 10 * decade
}

// Camera planes are a function of world size, not constants: a far plane fixed
// at 5000 m silently clips a world the scale gate told the operator to build.
// MAX_ORBIT_FACTOR caps how far the reviewer may dolly out (in extents), which
// is what makes the far plane provable rather than guessed — nothing can ever be
// further away than the orbit cap plus the world's own half-diagonal.
const MAX_ORBIT_FACTOR = 12
const FAR_MARGIN = 1.05

/**
 * Camera near/far planes and the orbit cap for a world of this half-extent, all
 * in metres.
 *
 * `near` is one block — the finest thing that can exist — at every extent. With
 * a conventional depth buffer that would be reckless next to a far plane tens of
 * kilometres out, but the viewer runs a logarithmic depth buffer, which spends
 * precision evenly across the range instead of hoarding it near the eye. That is
 * what lets near and far be chosen independently, each for its own reason.
 */
export const cameraPlanesFor = extentMetres => {
  const maxOrbit = extentMetres * MAX_ORBIT_FACTOR
  // √3·extent = half-diagonal of the buildable box (2E wide, 2E deep, 2E tall).
  const halfDiagonal = extentMetres * Math.sqrt(3)
  return {
    near: BLOCK_SIZE,
    far: (maxOrbit + halfDiagonal) * FAR_MARGIN,
    maxOrbit,
  }
}

// The opening camera as a multiple of the extent, not a fixed point: these are
// (42, 32, 54) over the 32 m world that framing was tuned on, so a 32 m world
// still opens exactly where it always did.
const CAMERA_START_RATIO = [42 / 32, 1, 54 / 32]

/** Opening camera position [x, y, z] in metres for a world of this half-extent. */
export const cameraStartFor = extentMetres => CAMERA_START_RATIO.map(k => k * extentMetres)

/** A configured gridStep wins; anything else (`auto`) derives from the extent. */
export const resolveGridStep = (configured, extentMetres) =>
  typeof configured === 'number' ? configured : gridStepFor(extentMetres)

/**
 * World bounds. extent and gridStep are in METRES (independent of BLOCK_SIZE);
 * the *Blocks getters convert to the integer block limits used for build bounds.
 */
export const WORLD = {
  extent: values.extent,
  /** Floor grid cell size in metres — derived unless config.yaml pins a number. */
  get gridStep() {
    return resolveGridStep(values.gridStep, this.extent)
  },
  /** Max |x| and |z| in blocks. */
  get boundBlocks() {
    return Math.round(this.extent / BLOCK_SIZE)
  },
  /** Max y in blocks (buildable height = 2×extent metres). */
  get heightBlocks() {
    return Math.round((this.extent * 2) / BLOCK_SIZE)
  },
  get nearPlane() {
    return cameraPlanesFor(this.extent).near
  },
  get farPlane() {
    return cameraPlanesFor(this.extent).far
  },
  /** How far the reviewer may dolly from the orbit target, in metres. */
  get maxOrbit() {
    return cameraPlanesFor(this.extent).maxOrbit
  },
  /** Opening camera position [x, y, z] in metres. */
  get cameraStart() {
    return cameraStartFor(this.extent)
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
