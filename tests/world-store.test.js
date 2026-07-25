import { describe, it, expect } from 'vitest'
import WorldStore from '../server/WorldStore.js'
import { applyBatch } from '../server/commands.js'
import { expand } from '../shared/protocol.js'

const boxPart = expand({ op: 'box', at: [0, 0, 0], size: [4, 4, 4], mat: 'oak' })[0]

describe('WorldStore', () => {
  it('assigns increasing ids and stores parts', () => {
    const s = new WorldStore()
    const a = s.add(boxPart)
    const b = s.add(boxPart)
    expect(a).toBe(1)
    expect(b).toBe(2)
    expect(s.size).toBe(2)
    expect(s.parts.get(a)).toMatchObject({ id: 1, kind: 'box', material: 'oak' })
  })
  it('removes by id and clears', () => {
    const s = new WorldStore()
    const id = s.add(boxPart)
    expect(s.remove(id)).toBe(true)
    expect(s.remove(id)).toBe(false)
    s.add(boxPart)
    s.clear()
    expect(s.size).toBe(0)
    expect(s.nextId).toBe(1)
  })
  it('snapshots all parts', () => {
    const s = new WorldStore()
    s.add(boxPart)
    s.add(boxPart)
    expect(s.snapshot()).toHaveLength(2)
    expect(s.snapshot()[0]).toHaveProperty('id')
  })
})

describe('applyBatch', () => {
  it('adds parts with ids and returns a diff', () => {
    const s = new WorldStore()
    const r = applyBatch(s, [
      { op: 'box', at: [0, 0, 0], size: [10, 20, 10], mat: 'oak' },
      { op: 'sphere', at: [5, 40, 5], r: 5, mat: 'glass' },
    ])
    expect(r.added).toHaveLength(2)
    expect(r.added[0].id).toBe(1)
    expect(r.errors).toHaveLength(0)
    expect(s.size).toBe(2)
  })
  it('rejects invalid commands without mutating', () => {
    const s = new WorldStore()
    const r = applyBatch(s, [{ op: 'box', at: [0, 0, 0], size: [1, 1, 1], mat: 'nope' }])
    expect(r.added).toHaveLength(0)
    expect(r.errors).toHaveLength(1)
    expect(s.size).toBe(0)
  })
  it('handles remove and clear', () => {
    const s = new WorldStore()
    applyBatch(s, [{ op: 'box', at: [0, 0, 0], size: [2, 2, 2], mat: 'oak' }])
    const rem = applyBatch(s, [{ op: 'remove', id: 1 }])
    expect(rem.removed).toEqual([1])
    applyBatch(s, [{ op: 'box', at: [0, 0, 0], size: [2, 2, 2], mat: 'oak' }])
    const cl = applyBatch(s, [{ op: 'clear' }])
    expect(cl.cleared).toBe(true)
    expect(s.size).toBe(0)
  })
})
