import {
  Scene, Color, PerspectiveCamera, WebGLRenderer,
  HemisphereLight, DirectionalLight, ACESFilmicToneMapping, SRGBColorSpace,
} from 'three'
import World from '../engine/World.js'
import Grid from './Grid.js'
import Hud from './Hud.js'
import CameraDirector from './CameraDirector.js'
import { bindControls } from './controls.js'
import { WORLD } from '@codeblox/shared/config.js'

const MAX_DT = 0.05 // clamp frame delta so a tab-switch doesn't fling the camera
const FALLBACK_BG = '#dde1e7'

// One source for the backdrop: read the CSS --color-bg token so the page and the
// 3D scene always match.
const readBg = () => {
  const v = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim()
  return new Color(v || FALLBACK_BG)
}

/**
 * Assembles the scene and drives the render loop. Owns the World (engine), the
 * Grid, the HUD, and the CameraDirector, and exposes the small surface the
 * keyboard controls and the local/ws driver call.
 */
export default class Viewer {
  constructor($container) {
    this.$container = $container

    this.scene = new Scene()
    this.scene.background = readBg()

    this.camera = new PerspectiveCamera(50, this._aspect(), WORLD.nearPlane, WORLD.farPlane)
    this.camera.position.set(...WORLD.cameraStart)

    // Logarithmic depth: the near/far span is a function of world extent, so at a
    // kilometre scale it is wide enough that a conventional depth buffer would
    // z-fight. This spends precision evenly across the range instead.
    this.renderer = new WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.setSize(this._w(), this._h())
    this.renderer.toneMapping = ACESFilmicToneMapping
    this.renderer.outputColorSpace = SRGBColorSpace
    $container.appendChild(this.renderer.domElement)

    this.scene.add(new HemisphereLight(0xbcccdc, 0x2a3038, 1.0))
    const key = new DirectionalLight(0xffffff, 1.15)
    key.position.set(0.6, 1, 0.4).multiplyScalar(100)
    this.scene.add(key)

    this.world = new World()
    this.scene.add(this.world.root)

    this.grid = new Grid(WORLD.extent, WORLD.gridStep)
    this.scene.add(this.grid.object3d)

    this.hud = new Hud($container)
    this.hud.setGrid(WORLD.extent)

    this.cameraDirector = new CameraDirector(this.camera, this.renderer.domElement, this.world)

    // The focus group: ids of the build currently landing, or null for "no build
    // in progress — frame the world". A build arrives as several batches over
    // several seconds, so the group is what turns that stream back into one
    // subject the camera can follow.
    this._focusIds = null

    this.world.onBuildBegin = () => {
      this._focusIds = new Set()
      this.cameraDirector.focusOn(null) // nothing landed yet
      this.cameraDirector.engageAgent()
      this.hud.toast('building')
    }

    this.world.onAdded = ids => {
      if (!this._focusIds) return
      for (const id of ids) this._focusIds.add(id)
      this.cameraDirector.focusOn(this.world.boundsOf(this._focusIds))
    }

    this.world.onClear = () => {
      // After a clear the build is all there is, so world framing already IS
      // build framing — holding a focus would only make it go stale.
      this._focusIds = null
      this.cameraDirector.focusOn(null)
      this.cameraDirector.engageAgent()
      this.hud.toast('cleared')
    }

    this._unbind = bindControls(this)
    this._onResize = () => this._resize()
    window.addEventListener('resize', this._onResize)

    this._raf = null
    this._last = 0
  }

  _w() { return this.$container.clientWidth || window.innerWidth }
  _h() { return this.$container.clientHeight || window.innerHeight }
  _aspect() { return this._w() / this._h() }

  start() {
    this._last = performance.now()
    const loop = t => {
      this._raf = requestAnimationFrame(loop)
      const now = t ?? performance.now()
      const dt = Math.min((now - this._last) / 1000, MAX_DT)
      this._last = now
      this.world.tickAnimations()
      this.cameraDirector.tick(dt)
      this.hud.update(this.world.getStats(), {
        mode: this.cameraDirector.mode,
        view: this.cameraDirector.view,
      })
      this.renderer.render(this.scene, this.camera)
    }
    this._raf = requestAnimationFrame(loop)
    return this
  }

  // --- control surface (keyboard + driver) ---------------------------------

  /**
   * Apply the viewer ops relayed with a diff. Callers invoke this *after* the
   * world diff has been applied — that is the protocol's ordering rule, and it
   * is the caller's statement order that enforces it.
   *
   * Every op routes to the same setter the keyboard uses, so there is one
   * behaviour per action rather than an agent path and a human path that drift.
   */
  applyViewerOps(ops = []) {
    for (const cmd of ops) {
      switch (cmd.op) {
        case 'view':
          // hold: the agent is directing, not taking over. See CameraDirector.
          this.viewFrom(cmd.n, { hold: true })
          break
        case 'reframe':
          this.reframe()
          break
        case 'rotate':
          this.setRotate(cmd.on, { grab: false })
          break
        case 'grid':
          this.setGridVisible(cmd.on)
          break
        case 'hud':
          this.setHudVisible(cmd.on)
          break
      }
    }
  }

  reframe() {
    this._focusIds = null
    this.cameraDirector.reframe()
    this.hud.toast('reframed')
  }

  setRotate(on, opts) {
    this.cameraDirector.setRotate(on, opts)
    this.hud.toast(`auto-rotate ${on ? 'on' : 'off'}`)
  }

  toggleRotate() {
    this.setRotate(!this.cameraDirector.autoRotate)
  }

  setGridVisible(on) {
    this.grid.visible = on
    this.hud.toast(`grid ${on ? 'on' : 'off'}`)
  }

  toggleGrid() {
    this.setGridVisible(!this.grid.visible)
  }

  // No toast: it would be drawn inside the panel that just went away.
  setHudVisible(on) {
    this.hud.visible = on
  }

  toggleHud() {
    this.setHudVisible(!this.hud.visible)
  }

  viewFrom(n, opts) {
    const name = this.cameraDirector.viewFrom(n, opts)
    if (name) this.hud.toast(`view: ${name}`) // null = already in that view
  }

  _resize() {
    this.camera.aspect = this._aspect()
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(this._w(), this._h())
  }

  dispose() {
    if (this._raf) cancelAnimationFrame(this._raf)
    this._unbind?.()
    window.removeEventListener('resize', this._onResize)
    this.renderer.dispose()
  }
}
