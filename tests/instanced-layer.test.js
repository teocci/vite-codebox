import { describe, it, expect } from 'vitest'
import { BoxGeometry, MeshBasicMaterial, Matrix4, Color } from 'three'
import InstancedLayer from '../apps/web/src/engine/InstancedLayer.js'

// InstancedMesh writes to typed arrays without a GL context, so this runs headless.
const geo = new BoxGeometry(1, 1, 1)
const mat = () => new MeshBasicMaterial()

// Encode an id into a matrix so we can verify which instance sits in which slot.
const mtx = id => new Matrix4().makeTranslation(id, 0, 0)
const readX = (layer, id) => {
  const m = layer.getMatrix(id, new Matrix4())
  return m ? m.elements[12] : null
}

describe('InstancedLayer add/remove', () => {
  it('adds instances and preserves each id -> matrix', () => {
    const layer = new InstancedLayer(geo, mat(), 8)
    for (let id = 0; id < 5; id++) layer.add(id, mtx(id), 0xffffff)
    expect(layer.count).toBe(5)
    for (let id = 0; id < 5; id++) expect(readX(layer, id)).toBe(id)
  })

  it('swap-removes a middle id in O(1) without disturbing the others', () => {
    const layer = new InstancedLayer(geo, mat(), 8)
    for (let id = 0; id < 5; id++) layer.add(id, mtx(id), 0xffffff)
    // Remove id 1: the last instance (id 4) should move into its slot.
    const movedSlotBefore = layer.count - 1
    expect(layer.remove(1)).toBe(true)
    expect(layer.count).toBe(4)
    expect(layer.has(1)).toBe(false)
    // id 4 kept its matrix identity through the swap...
    expect(readX(layer, 4)).toBe(4)
    // ...and now occupies the freed slot (1), not the old tail slot.
    expect(layer.idToSlot.get(4)).toBe(1)
    expect(layer.idToSlot.get(4)).not.toBe(movedSlotBefore)
    // every surviving id still resolves correctly
    for (const id of [0, 2, 3, 4]) expect(readX(layer, id)).toBe(id)
  })

  it('removes the tail id without a swap', () => {
    const layer = new InstancedLayer(geo, mat(), 8)
    for (let id = 0; id < 3; id++) layer.add(id, mtx(id), 0xffffff)
    expect(layer.remove(2)).toBe(true)
    expect(layer.count).toBe(2)
    for (const id of [0, 1]) expect(readX(layer, id)).toBe(id)
  })

  it('carries color through a swap-remove', () => {
    const layer = new InstancedLayer(geo, mat(), 8)
    layer.add(10, mtx(10), 0x112233)
    layer.add(11, mtx(11), 0x445566)
    layer.add(12, mtx(12), 0x778899)
    layer.remove(10) // 12 swaps into slot 0
    const c = new Color()
    layer.mesh.getColorAt(layer.idToSlot.get(12), c)
    expect(c.getHex()).toBe(0x778899)
  })

  it('returns false when removing an unknown id', () => {
    const layer = new InstancedLayer(geo, mat(), 8)
    layer.add(1, mtx(1), 0xffffff)
    expect(layer.remove(999)).toBe(false)
    expect(layer.count).toBe(1)
  })

  it('grows capacity and preserves all instances', () => {
    const layer = new InstancedLayer(geo, mat(), 4)
    for (let id = 0; id < 10; id++) layer.add(id, mtx(id), 0xffffff)
    expect(layer.count).toBe(10)
    expect(layer.capacity).toBeGreaterThanOrEqual(10)
    for (let id = 0; id < 10; id++) expect(readX(layer, id)).toBe(id)
  })

  it('supports add-remove-add churn with stable identity', () => {
    const layer = new InstancedLayer(geo, mat(), 4)
    for (let id = 0; id < 6; id++) layer.add(id, mtx(id), 0xffffff)
    layer.remove(2)
    layer.remove(4)
    layer.add(100, mtx(100), 0xffffff)
    expect(layer.count).toBe(5)
    for (const id of [0, 1, 3, 5, 100]) expect(readX(layer, id)).toBe(id)
    expect(layer.has(2)).toBe(false)
    expect(layer.has(4)).toBe(false)
  })
})
