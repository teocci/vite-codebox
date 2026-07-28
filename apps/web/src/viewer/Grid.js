import { GridHelper, Group, Color } from 'three'

const CENTER_LINE = 0x7c828e
const GRID_LINE = 0xb7bcc4

/**
 * Floor grid, drawn in METRES so it stays a stable human reference regardless of
 * the (finer) block size. gridStep sets the cell size in metres.
 */
export default class Grid {
  constructor(extentMetres, gridStepMetres) {
    const size = extentMetres * 2
    const divisions = Math.max(1, Math.round(size / gridStepMetres))
    this.object3d = new Group()
    this.helper = new GridHelper(size, divisions, new Color(CENTER_LINE), new Color(GRID_LINE))
    this.object3d.add(this.helper)
  }

  get visible() {
    return this.object3d.visible
  }

  // Paired with the getter so an agent can say "grid off" and mean it. A blind
  // caller cannot read viewer state back — viewer state is not in world_info
  // and there is no read-back channel — so a toggle is unusable to it: sending
  // one twice lands wherever it started.
  set visible(on) {
    this.object3d.visible = on
  }

  toggle() {
    this.visible = !this.visible
    return this.visible
  }
}
