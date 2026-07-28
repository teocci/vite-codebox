import { VIEW_COUNT } from '@codeblox/shared/views.js'

/**
 * Keyboard controls for the human reviewer. Delegates to the viewer, which owns
 * the camera/grid/HUD and surfaces a toast for each action.
 *
 * The preset keys are derived from VIEW_COUNT rather than listed, so adding a
 * seventh view is one edit to the shared table instead of three that must agree
 * (the table, this switch, and the HUD hint).
 */
export const bindControls = viewer => {
  const onKey = e => {
    if (e.repeat) return // ignore auto-repeat from a held key
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const tag = e.target?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    const preset = Number(e.key)
    if (Number.isInteger(preset) && preset >= 1 && preset <= VIEW_COUNT) {
      viewer.viewFrom(preset)
      e.preventDefault()
      return
    }

    switch (e.key.toLowerCase()) {
      case 'f':
        viewer.reframe()
        break
      case 'r':
        viewer.toggleRotate()
        break
      case 'g':
        viewer.toggleGrid()
        break
      case 'h':
        viewer.toggleHud()
        break
      default:
        return
    }
    e.preventDefault()
  }

  window.addEventListener('keydown', onKey)
  return () => window.removeEventListener('keydown', onKey)
}
