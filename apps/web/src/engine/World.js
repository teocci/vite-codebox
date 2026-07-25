import { Group, Matrix4, Vector3, Quaternion } from 'three'
import { makeGeometries } from './geometry.js'
import { makeFamilyMaterial } from './materials.js'
import InstancedLayer from './InstancedLayer.js'
import DropAnimator from './DropAnimator.js'
import { BLOCK_SIZE } from '@codeblox/shared/config.js'
import { materialColor, materialFamily } from '@codeblox/shared/materials.js'

const IDENTITY_QUAT = new Quaternion()

/** AABB of any iterable of parts, in block space. count 0 means "no parts". */
const aabbOf = parts => {
  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]
  let count = 0
  for (const p of parts) {
    count++
    for (let i = 0; i < 3; i++) {
      const lo = p.center[i] - p.size[i] / 2
      const hi = p.center[i] + p.size[i] / 2
      if (lo < min[i]) min[i] = lo
      if (hi > max[i]) max[i] = hi
    }
  }
  return count ? { min, max, count } : { min: [0, 0, 0], max: [0, 0, 0], count: 0 }
}

/**
 * Bounding sphere of any iterable of parts, for camera framing. Shared by the
 * whole-world bounds and the per-build focus bounds so there is one piece of
 * framing math, not two that can disagree.
 */
const sphereOf = parts => {
  const { min, max, count } = aabbOf(parts)
  if (count === 0) return { center: [0, 0, 0], radius: 0 }
  return {
    center: [0, 1, 2].map(i => (min[i] + max[i]) / 2),
    radius: 0.5 * Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]),
  }
}

/**
 * The viewer's world: the semantic parts map plus the instanced render layers.
 * Consumes normalized diffs ({ added, removed, cleared }) — the exact shape the
 * server will later broadcast, so the transport can be added without touching this.
 *
 * Rendering runs in block space; the root group is scaled by BLOCK_SIZE so that
 * single dial converts everything to metres at the boundary.
 */
export default class World {
  constructor({ now } = {}) {
    this.root = new Group()
    this.root.scale.setScalar(BLOCK_SIZE)
    this.geometries = makeGeometries()
    this.familyMaterials = new Map() // family -> shared THREE material
    this.layers = new Map() // "kind:family" -> InstancedLayer
    this.parts = new Map() // id -> { id, kind, center, size, material, layerKey }
    this.nextId = 1
    this.animator = new DropAnimator((layerKey, id, m) => this.layers.get(layerKey)?.setMatrix(id, m), now)
    this.onChange = null
    this.onClear = null
    this.onBuildBegin = null
    this.onAdded = null
    this._stats = null
    this._bounds = null
    this._m = new Matrix4()
    this._pos = new Vector3()
    this._scale = new Vector3()
  }

  // --- diff application -----------------------------------------------------

  applyDiff({ added = [], removed = [], cleared = false, buildBegin = false, animate = true } = {}) {
    // Fires before anything is applied so a listener can reset per-build state
    // (the camera's focus group) and then receive that build's ids via onAdded.
    if (buildBegin) this.onBuildBegin?.()
    if (cleared) this.clear()
    const removedIds = []
    for (const spec of removed) {
      const id = typeof spec === 'object' ? spec.id : spec
      if (this.removePart(id)) removedIds.push(id)
    }
    const addedIds = []
    added.forEach((part, i) => addedIds.push(this.addPart(part, i, animate)))
    this._invalidate()
    this.onChange?.()
    if (addedIds.length) this.onAdded?.(addedIds)
    return { addedIds, removedIds, cleared }
  }

  addPart(part, index = 0, animate = true) {
    const id = part.id ?? this.nextId++
    if (part.id != null && part.id >= this.nextId) this.nextId = part.id + 1

    const family = materialFamily(part.material) ?? 'opaque'
    const layerKey = `${part.kind}:${family}`
    const layer = this._layer(part.kind, family, layerKey)
    const target = this._compose(part.center, part.size)
    layer.add(id, target, materialColor(part.material) ?? 0xffffff)
    if (animate) this.animator.drop(id, layerKey, target, index)

    this.parts.set(id, { id, kind: part.kind, center: part.center, size: part.size, material: part.material, layerKey })
    return id
  }

  removePart(id) {
    const part = this.parts.get(id)
    if (!part) return false
    this.animator.cancel(id)
    this.layers.get(part.layerKey)?.remove(id)
    this.parts.delete(id)
    return true
  }

  clear() {
    for (const layer of this.layers.values()) {
      this.root.remove(layer.object3d)
      layer.dispose()
    }
    this.layers.clear()
    this.parts.clear()
    this.animator.clear()
    this.nextId = 1
    this._invalidate()
    this.onClear?.()
  }

  tickAnimations() {
    this.animator.tick()
  }

  // --- rendering helpers ----------------------------------------------------

  _layer(kind, family, layerKey) {
    let layer = this.layers.get(layerKey)
    if (layer) return layer
    let material = this.familyMaterials.get(family)
    if (!material) {
      material = makeFamilyMaterial(family)
      this.familyMaterials.set(family, material)
    }
    layer = new InstancedLayer(this.geometries[kind], material)
    this.root.add(layer.object3d)
    this.layers.set(layerKey, layer)
    return layer
  }

  _compose(center, size) {
    this._pos.set(center[0], center[1], center[2])
    this._scale.set(size[0], size[1], size[2])
    return this._m.compose(this._pos, IDENTITY_QUAT, this._scale)
  }

  // --- stats / bounds (cached; recomputed on change) ------------------------

  _invalidate() {
    this._stats = null
    this._bounds = null
  }

  getStats() {
    if (this._stats) return this._stats
    const { min, max } = aabbOf(this.parts.values())
    const mats = new Set()
    for (const p of this.parts.values()) mats.add(p.material)
    this._stats = {
      count: this.parts.size,
      materialsUsed: mats.size,
      layers: this.layers.size,
      min,
      max,
      extent: [max[0] - min[0], max[1] - min[1], max[2] - min[2]],
    }
    return this._stats
  }

  /** Bounding sphere of the whole world in block space, for camera framing. */
  getBounds() {
    this._bounds ??= sphereOf(this.parts.values())
    return this._bounds
  }

  /**
   * Bounding sphere of just these ids — what the camera frames while following
   * one build. Unknown ids are skipped, so a caller holding ids that have since
   * been removed still gets a usable sphere rather than a throw.
   */
  boundsOf(ids) {
    const parts = []
    for (const id of ids) {
      const part = this.parts.get(id)
      if (part) parts.push(part)
    }
    return sphereOf(parts)
  }
}
