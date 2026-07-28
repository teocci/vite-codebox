import styles from './Hud.module.css'
import { blockLabel, metres } from '@codeblox/shared/config.js'
import { MATERIAL_NAMES } from '@codeblox/shared/materials.js'
import { VIEW_COUNT } from '@codeblox/shared/views.js'

const fmt = n => {
  const r = Math.round(n * 10) / 10
  return Number.isInteger(r) ? String(r) : r.toFixed(1)
}

// Spaces around the separator are load-bearing, not decoration: they are the
// break opportunities that let a long triple wrap inside a bounded panel
// instead of widening it. A bare `×` makes the whole triple one unbreakable
// word, which is what `136850×11350×136850` was.
const TIMES = ' × '

/**
 * The extent in metres, exact. Never abbreviated — the scale gate (I-8) exists
 * to compare a build against the real subject's dimensions, and "2.7k m" cannot
 * be checked against 2737 m.
 */
export const extentMetresText = ([x, y, z]) =>
  `${fmt(metres(x))}${TIMES}${fmt(metres(y))}${TIMES}${fmt(metres(z))} m`

/** The same extent in whole blocks. Always 1/BLOCK_SIZE × the metre triple. */
export const extentBlocksText = ([x, y, z]) =>
  `${Math.round(x)}${TIMES}${Math.round(y)}${TIMES}${Math.round(z)}`

/**
 * Legend overlay: the reviewer's orientation. Kept tight — parts, extent in
 * metres, the same extent in blocks, grid, materials used, and who owns the
 * camera. All values are engine-internal, so textContent is safe (no untrusted
 * HTML).
 *
 * Extent gets two rows rather than one because BLOCK_SIZE is 0.02: the block
 * triple is by construction 50× the metre triple, so once either is large both
 * are, and no single row can hold them. One row fit only the 64 m world that
 * shipped before P-11.
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
      <div class="${styles.row}"><span class="${styles.label}">blocks</span><span class="${styles.value}" data-field="blocks">—</span></div>
      <div class="${styles.row}"><span class="${styles.label}">grid</span><span class="${styles.value}" data-field="grid">—</span></div>
      <div class="${styles.row}"><span class="${styles.label}">materials</span><span class="${styles.value}" data-field="materials">0 / ${MATERIAL_NAMES.length}</span></div>
      <div class="${styles.row}"><span class="${styles.label}">camera</span><span class="${styles.owner}"><span class="${styles.dot}"></span><span data-field="owner">AGENT</span></span></div>
      <div class="${styles.hint}">F reframe · R rotate · G grid · 1-${VIEW_COUNT} views · H hud</div>
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
    this.$('extent').textContent = stats.count ? extentMetresText(stats.extent) : '—'
    this.$('blocks').textContent = stats.count ? extentBlocksText(stats.extent) : '—'
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

  get visible() {
    return !this.$root.classList.contains(styles.hidden)
  }

  /** Idempotent, for the same reason Grid's is: an agent cannot read this back. */
  set visible(on) {
    this.$root.classList.toggle(styles.hidden, !on)
  }

  toggle() {
    this.visible = !this.visible
    return this.visible
  }
}
