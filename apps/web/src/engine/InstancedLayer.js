import { InstancedMesh, Matrix4, Color, DynamicDrawUsage } from 'three'

const INITIAL_CAPACITY = 256
const GROW_FACTOR = 2

/**
 * One InstancedMesh for a single (geometry x family), with O(1) add/remove.
 *
 * Removal uses swap-remove: the last live instance is copied into the freed slot
 * and count shrinks by one. That keeps the instance buffer packed with no rebuild,
 * so nothing else moves or re-animates. Because swap-remove changes which id owns
 * a slot, a bidirectional id<->slot index is maintained; the DropAnimator always
 * writes by id (resolving id->slot fresh) so a swap during a drop is handled.
 *
 * Capacity growth reallocates a 2x mesh and copies buffers — amortized O(1) per
 * add, a rare O(n) copy. This is the only non-O(1) path, and it never re-animates.
 */
export default class InstancedLayer {
  constructor(geometry, material, capacity = INITIAL_CAPACITY) {
    this.geometry = geometry
    this.material = material
    this.capacity = capacity
    this.count = 0
    this.idToSlot = new Map()
    this.slotToId = []
    this._m = new Matrix4()
    this._c = new Color()
    this.mesh = this._makeMesh(capacity)
  }

  _makeMesh(capacity) {
    const mesh = new InstancedMesh(this.geometry, this.material, capacity)
    mesh.count = this.count
    mesh.instanceMatrix.setUsage(DynamicDrawUsage)
    // A build grows unpredictably; skip frustum culling rather than recompute the
    // bounding sphere on every add.
    mesh.frustumCulled = false
    return mesh
  }

  get object3d() {
    return this.mesh
  }

  has(id) {
    return this.idToSlot.has(id)
  }

  /** Add an instance for id with the given matrix and hex color. */
  add(id, matrix, color) {
    if (this.idToSlot.has(id)) {
      this.setMatrix(id, matrix)
      this.setColor(id, color)
      return
    }
    if (this.count >= this.capacity) this._grow()
    const slot = this.count++
    this.idToSlot.set(id, slot)
    this.slotToId[slot] = id
    this.mesh.setMatrixAt(slot, matrix)
    if (color != null) this.mesh.setColorAt(slot, this._c.set(color))
    this.mesh.count = this.count
    this.mesh.instanceMatrix.needsUpdate = true
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true
  }

  /** Remove id's instance in O(1) via swap-remove. Returns true if it existed. */
  remove(id) {
    const slot = this.idToSlot.get(id)
    if (slot === undefined) return false
    const last = this.count - 1
    if (slot !== last) {
      this.mesh.getMatrixAt(last, this._m)
      this.mesh.setMatrixAt(slot, this._m)
      if (this.mesh.instanceColor) {
        this.mesh.getColorAt(last, this._c)
        this.mesh.setColorAt(slot, this._c)
      }
      const movedId = this.slotToId[last]
      this.slotToId[slot] = movedId
      this.idToSlot.set(movedId, slot)
    }
    this.slotToId.pop()
    this.idToSlot.delete(id)
    this.count = last
    this.mesh.count = this.count
    this.mesh.instanceMatrix.needsUpdate = true
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true
    return true
  }

  /** Overwrite id's matrix (used by the drop animation). No-op if absent. */
  setMatrix(id, matrix) {
    const slot = this.idToSlot.get(id)
    if (slot === undefined) return
    this.mesh.setMatrixAt(slot, matrix)
    this.mesh.instanceMatrix.needsUpdate = true
  }

  setColor(id, color) {
    const slot = this.idToSlot.get(id)
    if (slot === undefined || color == null) return
    this.mesh.setColorAt(slot, this._c.set(color))
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true
  }

  getMatrix(id, target) {
    const slot = this.idToSlot.get(id)
    if (slot === undefined) return null
    this.mesh.getMatrixAt(slot, target)
    return target
  }

  _grow() {
    const newCap = this.capacity * GROW_FACTOR
    const next = this._makeMesh(newCap)
    next.count = this.count
    for (let i = 0; i < this.count; i++) {
      this.mesh.getMatrixAt(i, this._m)
      next.setMatrixAt(i, this._m)
    }
    if (this.mesh.instanceColor) {
      for (let i = 0; i < this.count; i++) {
        this.mesh.getColorAt(i, this._c)
        next.setColorAt(i, this._c)
      }
    }
    next.instanceMatrix.needsUpdate = true
    if (next.instanceColor) next.instanceColor.needsUpdate = true
    const parent = this.mesh.parent
    if (parent) {
      parent.add(next)
      parent.remove(this.mesh)
    }
    this.mesh.dispose()
    this.mesh = next
    this.capacity = newCap
  }

  dispose() {
    this.mesh.dispose()
    this.idToSlot.clear()
    this.slotToId.length = 0
    this.count = 0
  }
}
