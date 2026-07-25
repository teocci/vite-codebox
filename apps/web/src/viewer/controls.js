/**
 * Keyboard controls for the human reviewer. Delegates to the viewer, which owns
 * the camera/grid/HUD and surfaces a toast for each action.
 */
export const bindControls = viewer => {
  const onKey = e => {
    if (e.repeat) return // ignore auto-repeat from a held key
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const tag = e.target?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

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
      case '1':
      case '2':
      case '3':
      case '4':
      case '5':
      case '6':
        viewer.viewFrom(Number(e.key))
        break
      default:
        return
    }
    e.preventDefault()
  }

  window.addEventListener('keydown', onKey)
  return () => window.removeEventListener('keydown', onKey)
}
