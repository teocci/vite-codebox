import {
  Scene, Color, PerspectiveCamera, WebGLRenderer,
  HemisphereLight, DirectionalLight, ACESFilmicToneMapping, SRGBColorSpace,
} from 'three'
import World from '../engine/World.js'
import Grid from './Grid.js'
import Hud from './Hud.js'
import CameraDirector from './CameraDirector.js'
import { bindControls } from './controls.js'
import { WORLD } from '../../shared/config.js'

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

    this.camera = new PerspectiveCamera(50, this._aspect(), 0.1, 5000)
    this.camera.position.set(42, 32, 54)

    this.renderer = new WebGLRenderer({ antialias: true })
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

    this.world.onClear = () => {
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

  reframe() {
    this.cameraDirector.reframe()
    this.hud.toast('reframed')
  }

  toggleRotate() {
    const on = this.cameraDirector.toggleRotate()
    this.hud.toast(`auto-rotate ${on ? 'on' : 'off'}`)
  }

  toggleGrid() {
    const on = this.grid.toggle()
    this.hud.toast(`grid ${on ? 'on' : 'off'}`)
  }

  toggleHud() {
    this.hud.toggle()
  }

  viewFrom(n) {
    const name = this.cameraDirector.viewFrom(n)
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
