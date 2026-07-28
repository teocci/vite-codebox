import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { PerspectiveCamera, Vector3 } from 'three'
import CameraDirector from '../apps/web/src/viewer/CameraDirector.js'
import Grid from '../apps/web/src/viewer/Grid.js'
import WsClient from '../apps/web/src/net/WsClient.js'

/**
 * The viewer runs under `environment: 'node'`, so anything touching `document`
 * (Hud, Viewer) is out of reach here. CameraDirector and Grid are not: three's
 * math and GridHelper are pure JS, and OrbitControls only needs an element that
 * answers the listener calls it makes at construction.
 */
const stubEl = () => ({
  addEventListener() {},
  removeEventListener() {},
  setPointerCapture() {},
  releasePointerCapture() {},
  style: {},
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }),
  ownerDocument: { addEventListener() {}, removeEventListener() {} },
  getRootNode: () => ({ addEventListener() {}, removeEventListener() {} }),
})

// A world whose bounds can grow, which is what a build arriving in stages does.
const stubWorld = (radius = 10) => ({
  radius,
  getBounds() {
    return { center: [0, 0, 0], radius: this.radius }
  },
})

const director = world => new CameraDirector(new PerspectiveCamera(50, 1.5, 0.02, 5000), stubEl(), world)

/** Unit vector from the orbit target to the camera — the viewing angle. */
const angleOf = cd => new Vector3().copy(cd.camera.position).sub(cd.controls.target).normalize()

const settle = (cd, frames = 60) => {
  for (let i = 0; i < frames; i++) cd.tick(0.05)
}

describe('CameraDirector.viewFrom', () => {
  it('hands the camera to the user by default — a human pressing 1 means it', () => {
    const cd = director(stubWorld())
    expect(cd.viewFrom(1)).toBe('three-quarter')
    expect(cd.mode).toBe('user')
    expect(cd.view).toBe('three-quarter')
  })

  it('keeps agent framing under hold — an agent is directing, not taking over', () => {
    const cd = director(stubWorld())
    expect(cd.viewFrom(1, { hold: true })).toBe('three-quarter')
    expect(cd.mode).toBe('agent')
    expect(cd.view).toBe('three-quarter')
  })

  it('preserves an agent-set angle while refitting as the build grows', () => {
    // The whole point of hold. tick() re-derives direction from the camera's own
    // position and corrects only distance and target, so stage 2..N stay framed
    // at the chosen angle instead of drifting out of frame.
    // Both radii are above MIN_RADIUS_METRES / BLOCK_SIZE, so the framer is
    // fitting the build rather than the floor it uses for an empty world.
    const world = stubWorld(100)
    const cd = director(world)
    cd.viewFrom(1, { hold: true })
    const angle = angleOf(cd)
    const near = cd.camera.position.distanceTo(cd.controls.target)

    world.radius = 1000 // the build keeps landing
    settle(cd)

    expect(angleOf(cd).angleTo(angle)).toBeLessThan(1e-3) // same angle
    expect(cd.camera.position.distanceTo(cd.controls.target)).toBeGreaterThan(near * 5)
  })

  it('lets the build drift out of frame without hold — the behaviour hold exists to fix', () => {
    const world = stubWorld(100)
    const cd = director(world)
    cd.viewFrom(1) // human handoff: the framer stands down
    const distance = cd.camera.position.distanceTo(cd.controls.target)

    world.radius = 1000
    settle(cd)

    // USER mode means no refit at all — the camera stays where the snap put it.
    expect(cd.camera.position.distanceTo(cd.controls.target)).toBeCloseTo(distance, 3)
  })

  it('returns null rather than re-snapping to the view it is already in', () => {
    const cd = director(stubWorld())
    expect(cd.viewFrom(2, { hold: true })).toBe('front-low')
    expect(cd.viewFrom(2, { hold: true })).toBe(null) // callers skip the toast
  })

  it('returns null for a preset that does not exist', () => {
    expect(director(stubWorld()).viewFrom(99)).toBe(null)
  })
})

describe('CameraDirector.setRotate', () => {
  it('is idempotent, because the agent asking cannot read the state back', () => {
    const cd = director(stubWorld())
    cd.setRotate(true, { grab: false })
    cd.setRotate(true, { grab: false })
    expect(cd.autoRotate).toBe(true) // a toggle sent twice would be off
    cd.setRotate(false, { grab: false })
    expect(cd.autoRotate).toBe(false)
  })

  it('grabs for a human and does not for an agent', () => {
    const human = director(stubWorld())
    human.setRotate(true)
    expect(human.mode).toBe('user') // turntable is a review aid; the handoff is right

    const agent = director(stubWorld())
    agent.setRotate(true, { grab: false })
    expect(agent.mode).toBe('agent') // grabbing here would stand the framer down
  })

  it('keeps toggleRotate working the way the R key always did', () => {
    const cd = director(stubWorld())
    expect(cd.toggleRotate()).toBe(true)
    expect(cd.mode).toBe('user')
    expect(cd.toggleRotate()).toBe(false)
  })
})

describe('CameraDirector.engageAgent', () => {
  it('discards free, which names no angle', () => {
    const cd = director(stubWorld())
    cd._grab()
    expect(cd.view).toBe('free')
    cd.engageAgent()
    expect(cd.view).toBe('auto')
  })

  it('keeps a chosen preset name, because the angle really does persist', () => {
    // Relabelling this 'auto' would have the HUD report an unattended camera
    // while it is in fact holding the view the agent asked for.
    const cd = director(stubWorld())
    cd.viewFrom(5, { hold: true })
    cd.engageAgent()
    expect(cd.view).toBe('rear three-quarter')
    expect(cd.mode).toBe('agent')
  })
})

describe('Grid visibility', () => {
  it('exposes an idempotent setter beside the toggle', () => {
    const grid = new Grid(32, 1)
    grid.visible = false
    grid.visible = false
    expect(grid.visible).toBe(false) // a toggle sent twice would be back on
    grid.visible = true
    expect(grid.visible).toBe(true)
  })

  it('keeps toggle returning the new visibility', () => {
    const grid = new Grid(32, 1)
    expect(grid.toggle()).toBe(false)
    expect(grid.toggle()).toBe(true)
  })
})

describe('WsClient viewer relay', () => {
  let log

  beforeEach(() => {
    // WsClient derives its url from the page it was served by; connect() is
    // never called here, so no WebSocket is needed.
    vi.stubGlobal('location', { protocol: 'http:', hostname: 'localhost' })
    log = []
  })

  afterEach(() => vi.unstubAllGlobals())

  const client = () =>
    new WsClient(
      { applyDiff: d => log.push(`diff:${d.added?.length ?? 0}`) },
      { onViewer: ops => log.push(`viewer:${ops.map(o => o.op).join('+')}`) },
    )

  it('reports viewer ops after the world diff, never before', () => {
    // This ordering is the protocol's rule, not an implementation detail:
    // [{view:1}, box, clear] must land as clear -> box -> view.
    client()._onMessage({ type: 'diff', added: [{}], viewer: [{ op: 'view', n: 1 }] })
    expect(log).toEqual(['diff:1', 'viewer:view'])
  })

  it('passes the whole batch of viewer ops in order', () => {
    client()._onMessage({
      type: 'diff',
      added: [],
      viewer: [{ op: 'rotate', on: true }, { op: 'grid', on: false }],
    })
    expect(log).toEqual(['diff:0', 'viewer:rotate+grid'])
  })

  it('stays silent on a diff carrying no viewer ops', () => {
    client()._onMessage({ type: 'diff', added: [{}], viewer: [] })
    client()._onMessage({ type: 'diff', added: [{}] }) // pre-P-15 server, no field
    expect(log).toEqual(['diff:1', 'diff:1'])
  })
})
