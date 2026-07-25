import styles from './Hud.module.css'
import { blockLabel, metres } from '../../shared/config.js'
import { MATERIAL_NAMES } from '../../shared/materials.js'

const fmt = n => {
  const r = Math.round(n * 10) / 10
  return Number.isInteger(r) ? String(r) : r.toFixed(1)
}

/**
 * Legend overlay: the reviewer's orientation. Kept tight — parts, extent (blocks
 * and metres), grid, materials used, and who owns the camera. All values are
 * engine-internal, so textContent is safe (no untrusted HTML).
 */
export default class Hud {
  constructor($container) {
    this.$root = document.createElement('div')
    this.$root.className = styles.hud
    this.$root.innerHTML = this._template()
    $container.appendChild(this.$root)

    this.$toasts = document.createElement('div')
    this.$toasts.className = styles.toasts
    $container.appendChild(this.$toasts)

    this.$ = name => this.$root.querySelector(`[data-field="${name}"]`)
    this.$owner = this.$root.querySelector(`.${styles.owner}`)
    this._sig = ''
  }

  _template() {
    return `
      <div class="${styles.title}">
        <span class="${styles.brand}">codeblox</span>
        <span class="${styles.unit}">1 block = ${blockLabel()}</span>
      </div>
      <div class="${styles.row}"><span class="${styles.label}">parts</span><span class="${styles.value}" data-field="parts">0</span></div>
      <div class="${styles.row}"><span class="${styles.label}">extent</span><span class="${styles.value}" data-field="extent">—</span></div>
      <div class="${styles.row}"><span class="${styles.label}">grid</span><span class="${styles.value}" data-field="grid">—</span></div>
      <div class="${styles.row}"><span class="${styles.label}">materials</span><span class="${styles.value}" data-field="materials">0 / ${MATERIAL_NAMES.length}</span></div>
      <div class="${styles.row}"><span class="${styles.label}">camera</span><span class="${styles.owner}"><span class="${styles.dot}"></span><span data-field="owner">AGENT</span></span></div>
      <div class="${styles.hint}">F reframe · R rotate · G grid · 1-6 views · H hud</div>
    `
  }

  setGrid(extentMetres) {
    const span = extentMetres * 2
    this.$('grid').textContent = `${span} × ${span} m`
  }

  update(stats, cam) {
    const [ex, ey, ez] = stats.extent
    const sig = `${stats.count}|${ex},${ey},${ez}|${stats.materialsUsed}|${cam.mode}|${cam.view}`
    if (sig === this._sig) return
    this._sig = sig

    this.$('parts').textContent = String(stats.count)
    this.$('extent').textContent = stats.count
      ? `${Math.round(ex)}×${Math.round(ey)}×${Math.round(ez)} blk · ${fmt(metres(ex))}×${fmt(metres(ey))}×${fmt(metres(ez))} m`
      : '—'
    this.$('materials').textContent = `${stats.materialsUsed} / ${MATERIAL_NAMES.length}`

    const isUser = cam.mode === 'user'
    this.$owner.classList.toggle(styles.ownerUser, isUser)
    this.$('owner').textContent = `${isUser ? 'USER' : 'AGENT'} · ${cam.view}`
  }

  toast(message) {
    const el = document.createElement('div')
    el.className = styles.toast
    el.textContent = message
    el.addEventListener('animationend', () => el.remove())
    this.$toasts.appendChild(el)
  }

  toggle() {
    const visible = this.$root.classList.toggle(styles.hidden)
    return !visible
  }
}
