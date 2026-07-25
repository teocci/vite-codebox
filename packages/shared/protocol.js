/**
 * Command protocol — the op vocabulary shared by the local driver, the server,
 * and (over the wire, via contract()) the Go CLI. Dependency-free.
 *
 * Coordinate convention: integer block coordinates, y-up.
 *   box      at = min corner,      size = [w,h,d]
 *   fill     from/to = inclusive corner cells        -> one box part
 *   sphere   at = center,          r                 (axis-aligned)
 *   cylinder at = center,          r, h              (axis = y in v1)
 *
 * Every part op normalizes to { kind, center, size, material } in block space,
 * where center is the geometry center and size is the full extent. The renderer
 * turns that into an instance matrix; BLOCK_SIZE is applied once by the viewer.
 */

import { WORLD } from './config.js'
import { isMaterial } from './materials.js'
import { blockLabel, BLOCK_SIZE } from './config.js'
import { MATERIALS } from './materials.js'

export const PART_OPS = new Set(['box', 'fill', 'sphere', 'cylinder'])

/**
 * Control ops carry no geometry. `build_begin` marks the start of one build — a
 * plan's worth of parts arriving over several batches — and touches no state:
 * it exists so a viewer can tell "these parts are the new thing" from "these
 * parts were already here". Without it the viewer sees only a stream of parts
 * and cannot group them, and no timing heuristic can recover the boundary,
 * because the gap between a build's own stages is unbounded.
 */
export const CONTROL_OPS = new Set(['remove', 'clear', 'world_info', 'build_begin'])

export const isPartOp = op => PART_OPS.has(op)
export const isControlOp = op => CONTROL_OPS.has(op)

/** Machine-readable field spec, published to schema-driven clients via contract(). */
export const OP_SCHEMA = [
  { op: 'box', fields: { at: 'int3', size: 'int3+', mat: 'material' } },
  { op: 'fill', fields: { from: 'int3', to: 'int3', mat: 'material' } },
  { op: 'sphere', fields: { at: 'int3', r: 'int+', mat: 'material' } },
  { op: 'cylinder', fields: { at: 'int3', r: 'int+', h: 'int+', mat: 'material' } },
  { op: 'remove', fields: { id: 'id' } },
  { op: 'clear', fields: {} },
  { op: 'world_info', fields: {} },
  { op: 'build_begin', fields: {} },
]

// --- validation helpers -----------------------------------------------------

const isInt = n => Number.isInteger(n)
const isPosInt = n => Number.isInteger(n) && n > 0
const isInt3 = v => Array.isArray(v) && v.length === 3 && v.every(isInt)

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
    case 'cylinder': {
      const d = cmd.r * 2
      return { kind: 'cylinder', center: [...cmd.at], size: [d, cmd.h, d], material: cmd.mat }
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
  if (typeof op !== 'string' || (!PART_OPS.has(op) && !CONTROL_OPS.has(op))) {
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
    case 'cylinder':
      if (!isInt3(cmd.at)) errors.push('at must be 3 integers')
      if (!isPosInt(cmd.r)) errors.push('r must be a positive integer')
      if (!isPosInt(cmd.h)) errors.push('h must be a positive integer')
      break
    case 'remove':
      if (!isInt(cmd.id) || cmd.id < 0) errors.push('id must be a non-negative integer')
      break
    case 'clear':
    case 'world_info':
    case 'build_begin':
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
