import { Vector3, MathUtils } from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { BLOCK_SIZE, WORLD } from '@codeblox/shared/config.js'

const PADDING = 1.3
const MIN_RADIUS_METRES = 1.0 // frame an empty/tiny world to something sensible
const EASE_K = 6 // higher = snappier agent-follow

// Canned review angles: [azimuth°, elevation°, name]. Together they cover
// front / side / plan / back / massing — no blind side.
const VIEWS = {
  1: [45, 25, 'three-quarter'], // front hero
  2: [0, 12, 'front-low'], // front silhouette
  3: [90, 12, 'side-low'], // side silhouette
  4: [0, 89, 'top-down'], // plan
  5: [225, 25, 'rear three-quarter'], // the other side
  6: [40, 58, "bird's-eye"], // high angle — massing + footprint
}

/**
 * Owns the camera. In AGENT mode an auto-framer eases the camera to fit the build
 * at the current angle; the instant the human touches the canvas it flips to USER
 * mode and the framer stands down, so it never fights the reviewer's zoom.
 *
 * The framer fits `focusBounds` when one is set and the whole world otherwise.
 * A focus is what makes "frame the new building" different from "frame
 * everything": with two builds far apart, fitting the world shows two specks.
 * The caller supplies a finished sphere, not a set of ids, so the framing math
 * runs once per landed stage rather than once per frame.
 */
export default class CameraDirector {
  constructor(camera, domElement, world) {
    this.camera = camera
    this.world = world
    this.mode = 'agent'
    this.view = 'auto'
    this.focusBounds = null
    this.controls = new OrbitControls(camera, domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.09
    this.controls.autoRotateSpeed = 1.1
    // The far plane is derived from this cap, so honouring it here is what makes
    // "the world never clips away" true rather than merely likely.
    this.controls.maxDistance = WORLD.maxOrbit

    this._center = new Vector3()
    this._dir = new Vector3()
    this._desired = new Vector3()
    this._tmp = new Vector3()

    const grab = () => this._grab()
    domElement.addEventListener('pointerdown', grab)
    domElement.addEventListener('wheel', grab, { passive: true })
    domElement.addEventListener('touchstart', grab, { passive: true })
  }

  _grab() {
    if (this.mode !== 'user') {
      this.mode = 'user'
      this.view = 'free'
    }
  }

  engageAgent() {
    this.mode = 'agent'
    this.view = 'auto'
  }

  /** Frame this sphere instead of the world. `null` restores whole-world framing. */
  focusOn(bounds) {
    this.focusBounds = bounds?.radius ? bounds : null
  }

  get autoRotate() {
    return this.controls.autoRotate
  }

  /** Distance at which a sphere of `radiusMetres` fills the frame. */
  _fitDistance(radiusMetres) {
    const vHalf = MathUtils.degToRad(this.camera.fov) / 2
    const hHalf = Math.atan(Math.tan(vHalf) * this.camera.aspect)
    const half = Math.min(vHalf, hHalf)
    return (radiusMetres * PADDING) / Math.sin(half)
  }

  _framedBounds() {
    const b = this.focusBounds ?? this.world.getBounds()
    this._center.set(b.center[0], b.center[1], b.center[2]).multiplyScalar(BLOCK_SIZE)
    return Math.max(b.radius * BLOCK_SIZE, MIN_RADIUS_METRES)
  }

  tick(dt) {
    if (this.mode === 'agent') {
      const radius = this._framedBounds()
      const distance = this._fitDistance(radius)
      // preserve the current viewing angle
      this._dir.copy(this.camera.position).sub(this.controls.target)
      if (this._dir.lengthSq() < 1e-6) this._dir.set(0.6, 0.5, 0.8)
      this._dir.normalize()
      this._desired.copy(this._center).addScaledVector(this._dir, distance)
      const a = 1 - Math.exp(-EASE_K * dt)
      this.camera.position.lerp(this._desired, a)
      this.controls.target.lerp(this._center, a)
    }
    this.controls.update()
  }

  /**
   * F: drop any focus and refit the whole world at the current angle, then let
   * the agent-framer keep following. "Show me everything" is the complement to
   * the build-scoped framing, and the only way back out to it.
   */
  reframe() {
    this.focusOn(null)
    this.engageAgent()
  }

  toggleRotate() {
    this.controls.autoRotate = !this.controls.autoRotate
    if (this.controls.autoRotate) this._grab() // turntable is a USER-mode review aid
    return this.controls.autoRotate
  }

  /**
   * Snap to a canned angle, fitted; hands control to the user. Returns the view
   * name if it changed, or null if already in that view (so callers can skip a
   * redundant toast).
   */
  viewFrom(n) {
    const preset = VIEWS[n]
    if (!preset) return null
    const [azDeg, elDeg, name] = preset
    if (this.mode === 'user' && this.view === name) return null // already there
    // Honours the focus: a canned angle reviews whatever is currently framed,
    // which right after a build is that build.
    const radius = this._framedBounds()
    const distance = this._fitDistance(radius)
    const az = MathUtils.degToRad(azDeg)
    const el = MathUtils.degToRad(elDeg)
    this._dir.set(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el))
    this.camera.position.copy(this._center).addScaledVector(this._dir, distance)
    this.controls.target.copy(this._center)
    this.controls.update()
    this.mode = 'user'
    this.view = name
    return name
  }
}
