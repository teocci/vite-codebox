import { describe, it, expect } from 'vitest'
import {
  BLOCK_SIZE, metres, blockLabel, WORLD,
  gridStepFor, cameraPlanesFor, cameraStartFor, resolveGridStep,
} from '@codeblox/shared/config.js'
import {
  MATERIALS, MATERIAL_NAMES, MATERIAL_FAMILIES, isMaterial, materialColor, materialFamily,
} from '@codeblox/shared/materials.js'
import { FAMILY, isFamily } from '@codeblox/shared/families.js'
import { validate, expand, contract, isPartOp } from '@codeblox/shared/protocol.js'

describe('config', () => {
  it('uses a 2 cm block by default', () => {
    expect(BLOCK_SIZE).toBe(0.02)
    expect(metres(50)).toBeCloseTo(1)
  })
  it('formats the block label in cm below 1 m (float-safe)', () => {
    expect(blockLabel()).toBe('2 cm')
  })
  it('derives block bounds from the metre extent', () => {
    expect(WORLD.boundBlocks).toBe(Math.round(WORLD.extent / BLOCK_SIZE))
    expect(WORLD.heightBlocks).toBe(Math.round((WORLD.extent * 2) / BLOCK_SIZE))
  })
})

describe('grid step derivation', () => {
  it('keeps the 1 m cell a 32 m world already had', () => {
    expect(gridStepFor(32)).toBe(1)
  })
  it('climbs the 1-2-5 ladder so a kilometre world is not 2800 cells across', () => {
    expect(gridStepFor(1400)).toBe(50)
    expect(gridStepFor(100)).toBe(5)
    expect(gridStepFor(640)).toBe(20)
  })
  it('descends below a metre for a room-sized world', () => {
    expect(gridStepFor(1)).toBeCloseTo(0.05)
  })
  it('holds the cell count in a readable band across four decades of extent', () => {
    for (const extent of [1, 10, 32, 100, 640, 1400, 5000]) {
      const divisions = (extent * 2) / gridStepFor(extent)
      expect(divisions).toBeGreaterThanOrEqual(25)
      expect(divisions).toBeLessThanOrEqual(70)
    }
  })
})

describe('camera plane derivation', () => {
  const EXTENTS = [1, 32, 100, 640, 1400, 5000]

  it('keeps the whole world inside the far plane at maximum orbit', () => {
    // The guarantee that makes a big extent usable: the user cannot dolly to a
    // distance where the far corner of the world clips away.
    for (const extent of EXTENTS) {
      const { far, maxOrbit } = cameraPlanesFor(extent)
      expect(far).toBeGreaterThan(maxOrbit + extent * Math.sqrt(3))
    }
  })
  it('pushes the far plane past the 5000 that clipped a kilometre world', () => {
    expect(cameraPlanesFor(1400).far).toBeGreaterThan(5000)
  })
  it('never moves the near plane further out than the 0.1 it used to be', () => {
    for (const extent of EXTENTS) {
      expect(cameraPlanesFor(extent).near).toBeLessThanOrEqual(0.1)
    }
  })
  it('holds the near plane at one block at every extent', () => {
    // A logarithmic depth buffer carries the precision, so near no longer has to
    // be traded against far: it can just be the finest thing that exists.
    for (const extent of EXTENTS) {
      expect(cameraPlanesFor(extent).near).toBe(BLOCK_SIZE)
    }
  })
  it('improves on the depth ratio the fixed planes gave a 32 m world', () => {
    const { near, far } = cameraPlanesFor(32)
    expect(far / near).toBeLessThan(5000 / 0.1)
  })
})

describe('opening camera position', () => {
  it('reproduces the framing a 32 m world opened on', () => {
    const [x, y, z] = cameraStartFor(32)
    expect(x).toBeCloseTo(42)
    expect(y).toBeCloseTo(32)
    expect(z).toBeCloseTo(54)
  })
  it('opens outside the world rather than buried inside it', () => {
    // The fixed 75 m position put a 1400 m world's opening camera below the
    // floor grid, looking at nothing.
    for (const extent of [1, 32, 1400, 5000]) {
      const [x, y, z] = cameraStartFor(extent)
      expect(Math.hypot(x, y, z)).toBeGreaterThan(extent)
    }
  })
  it('stays within the orbit cap it will be clamped to', () => {
    for (const extent of [1, 32, 1400, 5000]) {
      const [x, y, z] = cameraStartFor(extent)
      expect(Math.hypot(x, y, z)).toBeLessThan(cameraPlanesFor(extent).maxOrbit)
    }
  })
})

describe('WORLD resolves the derived values for the configured extent', () => {
  it('lets an explicit gridStep override the ladder', () => {
    expect(resolveGridStep(2, 1400)).toBe(2)
  })
  it('derives the gridStep when the config says auto', () => {
    expect(resolveGridStep('auto', 1400)).toBe(50)
  })
  it('exposes a resolved numeric gridStep, never the literal auto', () => {
    expect(typeof WORLD.gridStep).toBe('number')
    expect(Number.isFinite(WORLD.gridStep)).toBe(true)
  })
  it('exposes camera planes and the orbit cap for the configured extent', () => {
    const { near, far, maxOrbit } = cameraPlanesFor(WORLD.extent)
    expect(WORLD.nearPlane).toBeCloseTo(near)
    expect(WORLD.farPlane).toBeCloseTo(far)
    expect(WORLD.maxOrbit).toBeCloseTo(maxOrbit)
  })
  it('exposes the opening camera position for the configured extent', () => {
    expect(WORLD.cameraStart).toEqual(cameraStartFor(WORLD.extent))
  })
})

describe('materials', () => {
  it('has exactly 100 named materials', () => {
    expect(MATERIAL_NAMES.length).toBe(100)
  })
  it('every family list references a real material and a valid family', () => {
    for (const [family, names] of Object.entries(MATERIAL_FAMILIES)) {
      expect(isFamily(family)).toBe(true)
      for (const name of names) {
        expect(isMaterial(name)).toBe(true)
        expect(materialFamily(name)).toBe(family)
      }
    }
  })
  it('defaults unlisted materials to opaque', () => {
    expect(materialFamily('granite')).toBe(FAMILY.OPAQUE)
    expect(materialFamily('glass')).toBe(FAMILY.GLASS)
    expect(materialFamily('gold')).toBe(FAMILY.METAL)
    expect(materialFamily('flame')).toBe(FAMILY.EMISSIVE)
  })
  it('rejects unknown names', () => {
    expect(isMaterial('pink3')).toBe(false)
    expect(materialColor('pink3')).toBe(null)
    expect(materialColor('oak')).toBe(0xc9a377)
  })
})

describe('protocol.validate', () => {
  it('accepts a well-formed box', () => {
    expect(validate({ op: 'box', at: [0, 0, 0], size: [10, 20, 10], mat: 'oak' }).ok).toBe(true)
  })
  it('rejects unknown material', () => {
    const r = validate({ op: 'box', at: [0, 0, 0], size: [1, 1, 1], mat: 'nope' })
    expect(r.ok).toBe(false)
    expect(r.errors.join()).toMatch(/material/)
  })
  it('rejects non-integer / non-positive size', () => {
    expect(validate({ op: 'box', at: [0, 0, 0], size: [1.5, 1, 1], mat: 'oak' }).ok).toBe(false)
    expect(validate({ op: 'box', at: [0, 0, 0], size: [0, 1, 1], mat: 'oak' }).ok).toBe(false)
  })
  it('rejects out-of-bounds parts', () => {
    const below = validate({ op: 'box', at: [0, -5, 0], size: [1, 1, 1], mat: 'oak' })
    expect(below.ok).toBe(false)
    // Derived from the configured bound, not a literal: a fixed magnitude only
    // reads as "out of bounds" for the one extent it was written against.
    const tooWide = WORLD.boundBlocks * 4
    const wide = validate({ op: 'box', at: [0, 0, 0], size: [tooWide, 1, 1], mat: 'oak' })
    expect(wide.ok).toBe(false)
  })
  it('validates sphere and cylinder', () => {
    expect(validate({ op: 'sphere', at: [0, 5, 0], r: 5, mat: 'glass' }).ok).toBe(true)
    expect(validate({ op: 'cylinder', at: [0, 5, 0], r: 2, h: 10, mat: 'iron' }).ok).toBe(true)
    expect(validate({ op: 'sphere', at: [0, 5, 0], r: 0, mat: 'glass' }).ok).toBe(false)
  })
  it('validates ellipsoid, which takes a full extent rather than one radius', () => {
    expect(validate({ op: 'ellipsoid', at: [0, 20, 0], size: [8, 4, 12], mat: 'glass' }).ok).toBe(true)
    expect(validate({ op: 'ellipsoid', at: [0, 20, 0], size: [8, 0, 12], mat: 'glass' }).ok).toBe(false)
    expect(validate({ op: 'ellipsoid', at: [0, 20, 0], r: 4, mat: 'glass' }).ok).toBe(false)
  })
  it('validates tube, and refuses an axis that is not x, y or z', () => {
    for (const axis of ['x', 'y', 'z']) {
      expect(validate({ op: 'tube', at: [0, 20, 0], r: 5, h: 40, axis, mat: 'iron' }).ok).toBe(true)
    }
    const bad = validate({ op: 'tube', at: [0, 20, 0], r: 5, h: 40, axis: 'w', mat: 'iron' })
    expect(bad.ok).toBe(false)
    expect(bad.errors.join()).toMatch(/axis/)
    expect(validate({ op: 'tube', at: [0, 20, 0], r: 5, h: 40, mat: 'iron' }).ok).toBe(false)
  })
  it('validates control ops', () => {
    expect(validate({ op: 'clear' }).ok).toBe(true)
    expect(validate({ op: 'world_info' }).ok).toBe(true)
    expect(validate({ op: 'remove', id: 3 }).ok).toBe(true)
    expect(validate({ op: 'remove', id: -1 }).ok).toBe(false)
    expect(validate({ op: 'frobnicate' }).ok).toBe(false)
  })

  it('accepts build_begin, which carries no fields', () => {
    expect(validate({ op: 'build_begin' }).ok).toBe(true)
    expect(isPartOp('build_begin')).toBe(false)
    expect(expand({ op: 'build_begin' })).toEqual([])
  })
})

describe('protocol.expand', () => {
  it('normalizes a box to center + size', () => {
    const [p] = expand({ op: 'box', at: [0, 0, 0], size: [10, 20, 10], mat: 'oak' })
    expect(p).toEqual({ kind: 'box', center: [5, 10, 5], size: [10, 20, 10], material: 'oak' })
  })
  it('normalizes a sphere (at = center)', () => {
    const [p] = expand({ op: 'sphere', at: [5, 25, 5], r: 5, mat: 'glass' })
    expect(p).toEqual({ kind: 'sphere', center: [5, 25, 5], size: [10, 10, 10], material: 'glass' })
  })
  it('normalizes an inclusive fill region to one box', () => {
    const [p] = expand({ op: 'fill', from: [0, 0, 0], to: [2, 0, 2], mat: 'cobble' })
    expect(p.kind).toBe('box')
    expect(p.size).toEqual([3, 1, 3])
    expect(p.center).toEqual([1.5, 0.5, 1.5])
  })
  it('normalizes an ellipsoid onto the sphere geometry', () => {
    // kind is 'sphere' on purpose: the instance matrix already carries a
    // non-uniform scale, so three radii need no new geometry and no new layer.
    const [p] = expand({ op: 'ellipsoid', at: [5, 25, 5], size: [8, 4, 12], mat: 'glass' })
    expect(p).toEqual({ kind: 'sphere', center: [5, 25, 5], size: [8, 4, 12], material: 'glass' })
  })
  it('normalizes a tube by permuting its size onto the named axis', () => {
    const cases = {
      x: { kind: 'cylinder_x', size: [40, 10, 10] },
      y: { kind: 'cylinder', size: [10, 40, 10] },
      z: { kind: 'cylinder_z', size: [10, 10, 40] },
    }
    for (const [axis, want] of Object.entries(cases)) {
      const [p] = expand({ op: 'tube', at: [0, 50, 0], r: 5, h: 40, axis, mat: 'iron' })
      expect(p).toEqual({ ...want, center: [0, 50, 0], material: 'iron' })
    }
  })
  it('returns [] for control ops', () => {
    expect(expand({ op: 'clear' })).toEqual([])
    expect(isPartOp('clear')).toBe(false)
  })
})

describe('protocol.contract', () => {
  it('publishes config, palette and op schema', () => {
    const c = contract()
    expect(c.config.blockSize).toBe(0.02)
    expect(c.config.blockLabel).toBe('2 cm')
    expect(c.palette.oak).toEqual({ color: 0xc9a377, family: 'opaque' })
    expect(c.ops.find(o => o.op === 'box')).toBeTruthy()
  })

  it('publishes build_begin, so schema-driven clients can send it', () => {
    // The Go CLI validates against this payload; an unpublished op is refused
    // client-side and never reaches the server.
    expect(contract().ops.find(o => o.op === 'build_begin')).toEqual({
      op: 'build_begin',
      fields: {},
    })
  })
})
