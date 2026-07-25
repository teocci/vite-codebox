import { Matrix4, Vector3, Quaternion } from 'three'

const DROP_HEIGHT = 6 // blocks above the target to start the fall
const DROP_MS = 350
const STAGGER_MS = 18 // per-part delay so a batch cascades instead of popping

const easeOutCubic = t => 1 - Math.pow(1 - t, 3)

/**
 * Animates newly added parts falling into place. Only in-flight ids live in
 * `active`; settled parts are removed and never touched again — which is the
 * whole point: adding or removing elsewhere can never re-drop something at rest.
 *
 * Each tick writes by id through the injected `write(layerKey, id, matrix)`, so a
 * swap-remove that relocates a still-dropping part's slot is handled transparently.
 */
export default class DropAnimator {
  constructor(write, now = () => performance.now()) {
    this.write = write
    this.now = now
    this.active = new Map()
    this._m = new Matrix4()
    this._p = new Vector3()
  }

  get size() {
    return this.active.size
  }

  isActive(id) {
    return this.active.has(id)
  }

  /** Begin dropping id in from above. `target` is the settled matrix (block space). */
  drop(id, layerKey, target, index = 0) {
    const pos = new Vector3()
    const quat = new Quaternion()
    const scale = new Vector3()
    target.decompose(pos, quat, scale)
    this.active.set(id, {
      layerKey,
      startAt: this.now() + index * STAGGER_MS,
      pos,
      quat,
      scale,
      fromY: pos.y + DROP_HEIGHT,
      target: target.clone(),
    })
  }

  /** Advance all in-flight drops. No-op when nothing is falling. */
  tick() {
    if (this.active.size === 0) return
    const now = this.now()
    for (const [id, a] of this.active) {
      const elapsed = now - a.startAt
      if (elapsed <= 0) {
        this._p.set(a.pos.x, a.fromY, a.pos.z)
        this.write(a.layerKey, id, this._m.compose(this._p, a.quat, a.scale))
        continue
      }
      const t = elapsed / DROP_MS
      if (t >= 1) {
        this.write(a.layerKey, id, a.target) // exact final matrix, written once
        this.active.delete(id)
        continue
      }
      const y = a.fromY + (a.pos.y - a.fromY) * easeOutCubic(t)
      this._p.set(a.pos.x, y, a.pos.z)
      this.write(a.layerKey, id, this._m.compose(this._p, a.quat, a.scale))
    }
  }

  cancel(id) {
    this.active.delete(id)
  }

  clear() {
    this.active.clear()
  }
}
