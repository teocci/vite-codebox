import { describe, it, expect, beforeEach } from 'vitest'
import { Matrix4 } from 'three'
import World from '../apps/web/src/engine/World.js'
import { expand } from '@codeblox/shared/protocol.js'

// A manual clock so drop animations are deterministic in tests.
let t = 0
const now = () => t
const advance = ms => {
  t += ms
}
const settle = world => {
  advance(1000) // past DROP_MS + any stagger
  world.tickAnimations()
}

const box = (at, size, mat) => expand({ op: 'box', at, size, mat })[0]
const sphere = (at, r, mat) => expand({ op: 'sphere', at, r, mat })[0]

describe('World integration', () => {
  beforeEach(() => {
    t = 0
  })

  it('applies an added diff and reports stats + bounds', () => {
    const world = new World({ now })
    const { addedIds } = world.applyDiff({
      added: [box([-5, 0, -5], [10, 20, 10], 'oak'), sphere([0, 25, 0], 5, 'glass')],
    })
    expect(addedIds).toHaveLength(2)
    const s = world.getStats()
    expect(s.count).toBe(2)
    expect(s.materialsUsed).toBe(2)
    // box spans y 0..20, sphere spans y 20..30 -> extent height 30
    expect(s.max[1]).toBe(30)
    expect(s.min[1]).toBe(0)
    expect(world.getBounds().radius).toBeGreaterThan(0)
  })

  it('routes different families into separate layers', () => {
    const world = new World({ now })
    world.applyDiff({ added: [box([0, 0, 0], [2, 2, 2], 'oak'), box([4, 0, 0], [2, 2, 2], 'gold')] })
    // same kind (box), different families (opaque, metal) -> two layers
    expect(world.layers.has('box:opaque')).toBe(true)
    expect(world.layers.has('box:metal')).toBe(true)
  })

  it('does NOT re-animate settled parts when another is removed', () => {
    const world = new World({ now })
    const { addedIds } = world.applyDiff({
      added: [
        box([0, 0, 0], [4, 4, 4], 'oak'),
        box([8, 0, 0], [4, 4, 4], 'oak'),
        box([16, 0, 0], [4, 4, 4], 'oak'),
      ],
    })
    settle(world)
    expect(world.animator.size).toBe(0) // everything at rest

    // snapshot the survivors' matrices
    const layer = world.layers.get('box:opaque')
    const before = new Map()
    for (const id of addedIds) before.set(id, layer.getMatrix(id, new Matrix4()).clone())

    // remove the middle part
    const removedId = addedIds[1]
    world.applyDiff({ removed: [removedId] })

    // nothing re-dropped, and the survivors' transforms are byte-identical
    expect(world.animator.size).toBe(0)
    for (const id of addedIds) {
      if (id === removedId) continue
      const m = layer.getMatrix(id, new Matrix4())
      expect(m.elements).toEqual(Array.from(before.get(id).elements))
    }
    expect(world.getStats().count).toBe(2)
  })

  it('clears the world and fires onClear', () => {
    const world = new World({ now })
    let cleared = false
    world.onClear = () => {
      cleared = true
    }
    world.applyDiff({ added: [box([0, 0, 0], [2, 2, 2], 'oak')] })
    world.applyDiff({ cleared: true })
    expect(cleared).toBe(true)
    expect(world.parts.size).toBe(0)
    expect(world.layers.size).toBe(0)
    expect(world.getStats().count).toBe(0)
    expect(world.getBounds().radius).toBe(0)
  })

  it('fires onBuildBegin before the parts of that build arrive', () => {
    const world = new World({ now })
    const order = []
    world.onBuildBegin = () => order.push('begin')
    world.onAdded = ids => order.push(`added:${ids.length}`)

    world.applyDiff({ buildBegin: true, added: [box([0, 0, 0], [2, 2, 2], 'oak')] })

    // Order matters: a listener resets its focus group on begin, then collects
    // the ids. Reversed, the reset would throw the build's first stage away.
    expect(order).toEqual(['begin', 'added:1'])
  })

  it('does not fire onBuildBegin for ordinary diffs', () => {
    const world = new World({ now })
    let begins = 0
    world.onBuildBegin = () => begins++
    world.applyDiff({ added: [box([0, 0, 0], [2, 2, 2], 'oak')] })
    world.applyDiff({ cleared: true })
    expect(begins).toBe(0)
  })

  it('boundsOf frames only the given ids, not the whole world', () => {
    // The reported bug: a build lands far from an existing one, and framing the
    // world puts both on screen as specks instead of showing the new thing.
    const world = new World({ now })
    const { addedIds: near } = world.applyDiff({ added: [box([0, 0, 0], [4, 4, 4], 'oak')] })
    world.applyDiff({ added: [box([500, 0, 0], [4, 4, 4], 'oak')] })

    const whole = world.getBounds()
    const focused = world.boundsOf(near)

    expect(whole.radius).toBeGreaterThan(200)
    expect(focused.radius).toBeLessThan(10)
    expect(focused.center[0]).toBe(2) // the near box's own centre, not the midpoint
  })

  it('boundsOf skips ids that are gone rather than throwing', () => {
    const world = new World({ now })
    const { addedIds } = world.applyDiff({ added: [box([0, 0, 0], [4, 4, 4], 'oak')] })
    world.removePart(addedIds[0])
    expect(world.boundsOf(addedIds)).toEqual({ center: [0, 0, 0], radius: 0 })
  })

  it('drops new parts in and settles them (animator drains)', () => {
    const world = new World({ now })
    world.applyDiff({ added: [box([0, 0, 0], [2, 2, 2], 'oak'), box([4, 0, 0], [2, 2, 2], 'oak')] })
    expect(world.animator.size).toBe(2) // in-flight
    world.tickAnimations() // early: still falling
    expect(world.animator.size).toBeGreaterThan(0)
    settle(world)
    expect(world.animator.size).toBe(0) // settled, never touched again
  })
})
