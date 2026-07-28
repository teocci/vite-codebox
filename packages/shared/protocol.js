/**
 * Command protocol — the op vocabulary shared by the local driver, the server,
 * and (over the wire, via contract()) the Go CLI. Dependency-free.
 *
 * Coordinate convention: integer block coordinates, y-up.
 *   box       at = min corner,      size = [w,h,d]
 *   fill      from/to = inclusive corner cells       -> one box part
 *   sphere    at = center,          r                (axis-aligned)
 *   ellipsoid at = center,          size = [w,h,d]   -> a sphere with three radii
 *   cylinder  at = center,          r, h             (axis = y)
 *   tube      at = center,          r, h, axis       -> a cylinder about x, y or z
 *
 * `ellipsoid` and `tube` exist because the renderer could already draw both and
 * only the schema refused to describe them: the instance matrix carries a fully
 * non-uniform scale, so a unit sphere becomes any axis-aligned ellipsoid, and
 * three baked cylinder geometries cover the three axes. Neither needs rotation,
 * so parts stay axis-aligned and every AABB stays exact. They are new ops rather
 * than new fields on `sphere`/`cylinder` deliberately — the Go client requires
 * every declared field to be present, so widening an existing op would break
 * every command already written against it.
 *
 * Every part op normalizes to { kind, center, size, material } in block space,
 * where center is the geometry center and size is the full extent. The renderer
 * turns that into an instance matrix; BLOCK_SIZE is applied once by the viewer.
 *
 * Ordering: viewer ops apply AFTER the world diff, regardless of their position
 * in the batch. So [{op:'view',n:1}, box, clear] lands as clear -> box -> view.
 * This is a real semantic, not an accident of implementation — framing a build
 * you are about to erase is never what was meant.
 */

import { WORLD } from './config.js'
import { isMaterial } from './materials.js'
import { blockLabel, BLOCK_SIZE } from './config.js'
import { MATERIALS } from './materials.js'
import { VIEW_COUNT } from './views.js'

export const PART_OPS = new Set(['box', 'fill', 'sphere', 'ellipsoid', 'cylinder', 'tube'])

/** The axes a `tube` may run along, in the order its size triple is indexed. */
export const AXES = ['x', 'y', 'z']

/**
 * Control ops carry no geometry. `build_begin` marks the start of one build — a
 * plan's worth of parts arriving over several batches — and touches no state:
 * it exists so a viewer can tell "these parts are the new thing" from "these
 * parts were already here". Without it the viewer sees only a stream of parts
 * and cannot group them, and no timing heuristic can recover the boundary,
 * because the gap between a build's own stages is unbounded.
 */
export const CONTROL_OPS = new Set(['remove', 'clear', 'world_info', 'build_begin'])

/**
 * Viewer ops direct presentation. They touch no world state, so the server
 * relays them and never stores them — a third category rather than more control
 * ops, because "relay, don't store" is a different routing rule and both the
 * server and the viewer's local path need one predicate for it.
 *
 * Five explicit ops rather than one grouped `view {n?, rotate?, ...}`: the Go
 * client requires every declared field to be present, so an optional-field op
 * is unrepresentable there.
 */
export const VIEWER_OPS = new Set(['view', 'reframe', 'rotate', 'grid', 'hud'])

export const isPartOp = op => PART_OPS.has(op)
export const isControlOp = op => CONTROL_OPS.has(op)
export const isViewerOp = op => VIEWER_OPS.has(op)

/** Machine-readable field spec, published to schema-driven clients via contract(). */
export const OP_SCHEMA = [
  { op: 'box', fields: { at: 'int3', size: 'int3+', mat: 'material' } },
  { op: 'fill', fields: { from: 'int3', to: 'int3', mat: 'material' } },
  { op: 'sphere', fields: { at: 'int3', r: 'int+', mat: 'material' } },
  { op: 'ellipsoid', fields: { at: 'int3', size: 'int3+', mat: 'material' } },
  { op: 'cylinder', fields: { at: 'int3', r: 'int+', h: 'int+', mat: 'material' } },
  { op: 'tube', fields: { at: 'int3', r: 'int+', h: 'int+', axis: 'axis', mat: 'material' } },
  { op: 'remove', fields: { id: 'id' } },
  { op: 'clear', fields: {} },
  { op: 'world_info', fields: {} },
  { op: 'build_begin', fields: {} },
  { op: 'view', fields: { n: 'int+' } },
  { op: 'reframe', fields: {} },
  { op: 'rotate', fields: { on: 'bool' } },
  { op: 'grid', fields: { on: 'bool' } },
  { op: 'hud', fields: { on: 'bool' } },
]

// --- validation helpers -----------------------------------------------------

const isInt = n => Number.isInteger(n)
const isPosInt = n => Number.isInteger(n) && n > 0
const isInt3 = v => Array.isArray(v) && v.length === 3 && v.every(isInt)
const isBool = v => typeof v === 'boolean'

const half = (a, b, c) => [a / 2, b / 2, c / 2]

// --- normalization ----------------------------------------------------------

/** Convert a validated part command into a normalized part (no id assigned). */
const toPart = cmd => {
  switch (cmd.op) {
    case 'box': {
      const [x, y, z] = cmd.at
      const [w, h, d] = cmd.size
      return { kind: 'box', center: [x + w / 2, y + h / 2, z + d / 2], size: [w, h, d], material: cmd.mat }
    }
    case 'fill': {
      const min = [0, 1, 2].map(i => Math.min(cmd.from[i], cmd.to[i]))
      const ext = [0, 1, 2].map(i => Math.abs(cmd.to[i] - cmd.from[i]) + 1)
      return { kind: 'box', center: [0, 1, 2].map(i => min[i] + ext[i] / 2), size: ext, material: cmd.mat }
    }
    case 'sphere': {
      const d = cmd.r * 2
      return { kind: 'sphere', center: [...cmd.at], size: [d, d, d], material: cmd.mat }
    }
    case 'ellipsoid':
      // Reuses the sphere geometry and therefore its InstancedMesh: the unit
      // sphere is already scaled per instance, so three radii cost nothing.
      return { kind: 'sphere', center: [...cmd.at], size: [...cmd.size], material: cmd.mat }
    case 'cylinder': {
      const d = cmd.r * 2
      return { kind: 'cylinder', center: [...cmd.at], size: [d, cmd.h, d], material: cmd.mat }
    }
    case 'tube': {
      // The axis is carried by a pre-rotated geometry, not by the matrix, so the
      // size triple below IS the world AABB and partAabb stays exact.
      const d = cmd.r * 2
      const size = [d, d, d]
      size[AXES.indexOf(cmd.axis)] = cmd.h
      const kind = cmd.axis === 'y' ? 'cylinder' : `cylinder_${cmd.axis}`
      return { kind, center: [...cmd.at], size, material: cmd.mat }
    }
    default:
      return null
  }
}

/** AABB [min, max] of a normalized part, in block space. */
const partAabb = part => {
  const [hx, hy, hz] = half(...part.size)
  const [cx, cy, cz] = part.center
  return [
    [cx - hx, cy - hy, cz - hz],
    [cx + hx, cy + hy, cz + hz],
  ]
}

const withinBounds = part => {
  const [min, max] = partAabb(part)
  const b = WORLD.boundBlocks
  const h = WORLD.heightBlocks
  return (
    min[0] >= -b && max[0] <= b &&
    min[2] >= -b && max[2] <= b &&
    min[1] >= 0 && max[1] <= h
  )
}

// --- public API -------------------------------------------------------------

/**
 * Validate a command. Returns { ok, errors }. Cheap and side-effect free — the
 * CLI runs this client-side to fail fast; the server runs it as the authority.
 */
export const validate = cmd => {
  const errors = []
  if (cmd == null || typeof cmd !== 'object') return { ok: false, errors: ['command must be an object'] }
  const { op } = cmd
  if (typeof op !== 'string' || (!PART_OPS.has(op) && !CONTROL_OPS.has(op) && !VIEWER_OPS.has(op))) {
    return { ok: false, errors: [`unknown op: ${JSON.stringify(op)}`] }
  }

  switch (op) {
    case 'box':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isInt3(cmd.size) || !cmd.size?.every?.(isPosInt)) errors.push('size must be 3 positive integers')
      break
    case 'fill':
      if (!isInt3(cmd.from)) errors.push('from must be 3 integers')
      if (!isInt3(cmd.to)) errors.push('to must be 3 integers')
      break
    case 'sphere':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isPosInt(cmd.r)) errors.push('r must be a positive integer')
      break
    case 'ellipsoid':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isInt3(cmd.size) || !cmd.size?.every?.(isPosInt)) errors.push('size must be 3 positive integers')
      break
    case 'cylinder':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isPosInt(cmd.r)) errors.push('r must be a positive integer')
      if (!isPosInt(cmd.h)) errors.push('h must be a positive integer')
      break
    case 'tube':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isPosInt(cmd.r)) errors.push('r must be a positive integer')
      if (!isPosInt(cmd.h)) errors.push('h must be a positive integer')
      if (!AXES.includes(cmd.axis)) errors.push(`axis must be one of ${AXES.join(', ')}`)
      break
    case 'remove':
      if (!isInt(cmd.id) || cmd.id < 0) errors.push('id must be a non-negative integer')
      break
    case 'view':
      // Range-checked here so an out-of-range preset is a refusal, not a
      // silent no-op — the viewer's own lookup would just return null.
      if (!isPosInt(cmd.n) || cmd.n > VIEW_COUNT) errors.push(`n must be an integer 1..${VIEW_COUNT}`)
      break
    case 'rotate':
    case 'grid':
    case 'hud':
      if (!isBool(cmd.on)) errors.push('on must be true or false')
      break
    case 'clear':
    case 'world_info':
    case 'build_begin':
    case 'reframe':
      break
  }

  if (PART_OPS.has(op)) {
    if (!isMaterial(cmd.mat)) errors.push(`unknown material: ${JSON.stringify(cmd.mat)}`)
    if (errors.length === 0 && !withinBounds(toPart(cmd))) errors.push('part is out of world bounds')
  }

  return { ok: errors.length === 0, errors }
}

/**
 * Expand a validated part command into normalized parts (currently 1:1). Returns
 * [] for control ops. Caller assigns ids.
 */
export const expand = cmd => {
  if (!PART_OPS.has(cmd?.op)) return []
  const part = toPart(cmd)
  return part ? [part] : []
}

/** The full contract published to clients (config + palette + op schema). */
export const contract = () => ({
  config: {
    blockSize: BLOCK_SIZE,
    blockLabel: blockLabel(),
    extent: WORLD.extent,
    gridStep: WORLD.gridStep,
    boundBlocks: WORLD.boundBlocks,
    heightBlocks: WORLD.heightBlocks,
  },
  palette: MATERIALS,
  ops: OP_SCHEMA,
})
