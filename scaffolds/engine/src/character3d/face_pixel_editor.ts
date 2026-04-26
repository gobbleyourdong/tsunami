/**
 * Face pixel editor widget — minimal HTML grid for painting eye/mouth
 * stamps. Loads existing styles as presets, lets user click cells to
 * cycle slot, bake button regenerates the GPU buffer via setFacePixelData.
 *
 * Grid: 5x5 for eyes (centred so dx, dy ∈ [-2..+2]), 5x3 for mouth.
 * Each cell = a slot value. Click cycles: clear → pupil → eyewhite →
 * accent → tear → glow_core → mouth → clear. Right-click for fast clear.
 *
 * Slot id ↔ shader semantic ID is the same 0-5 numbering used in the
 * outline shader's stamp loop, so what you paint is what renders.
 */

import {
  EYE_STYLES, MOUTH_STYLES,
  type FacePixelGrid, type FacePixelSlot, type FacePixel,
} from './face_pixels'

// Deep snapshot of the canonical presets, captured at module load BEFORE
// any editor instance can mutate EYE_STYLES / MOUTH_STYLES. The "reset"
// button restores from this — even after persisted edits have been
// loaded back from localStorage.
function cloneGrid(g: FacePixelGrid): FacePixelGrid {
  return { ...g, pixels: g.pixels.map((p) => ({ ...p })) }
}
const ORIGINAL_EYE_STYLES   = EYE_STYLES.map(cloneGrid)
const ORIGINAL_MOUTH_STYLES = MOUTH_STYLES.map(cloneGrid)

export const STORAGE_KEY = 'facePixels.v1'

/** Serialize the current EYE / MOUTH style arrays into a JSON-safe shape.
 *  Round-trips perfectly via tryLoadFromStorage. */
export function snapshotStyles(): { eye: FacePixelGrid[]; mouth: FacePixelGrid[] } {
  return { eye: EYE_STYLES.map(cloneGrid), mouth: MOUTH_STYLES.map(cloneGrid) }
}

/** Load a saved snapshot from localStorage and overlay it onto the live
 *  EYE_STYLES / MOUTH_STYLES arrays. Validates count + shape; returns
 *  false on any mismatch so the canonical presets stay authoritative. */
export function tryLoadFromStorage(): boolean {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
    if (!raw) return false
    const data = JSON.parse(raw) as { eye?: FacePixelGrid[]; mouth?: FacePixelGrid[] }
    if (!Array.isArray(data?.eye) || !Array.isArray(data?.mouth)) return false
    if (data.eye.length !== EYE_STYLES.length || data.mouth.length !== MOUTH_STYLES.length) return false
    // Trust the structure but validate each entry has a pixels array.
    for (const g of [...data.eye, ...data.mouth]) {
      if (!Array.isArray(g?.pixels)) return false
    }
    for (let i = 0; i < EYE_STYLES.length; i++)   EYE_STYLES[i]   = cloneGrid(data.eye[i])
    for (let i = 0; i < MOUTH_STYLES.length; i++) MOUTH_STYLES[i] = cloneGrid(data.mouth[i])
    return true
  } catch {
    return false
  }
}

export function saveToStorage() {
  try {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshotStyles()))
  } catch {
    /* quota / private mode — ignore */
  }
}

// Slot palette for the editor — name + display swatch + semantic ID.
// IDs match the shader's stamp loop slot decoder.
const SLOTS: { id: number; label: FacePixelSlot | 'clear'; swatch: string }[] = [
  { id: -1, label: 'clear',     swatch: 'transparent' },
  { id:  0, label: 'pupil',     swatch: '#1a1530' },
  { id:  1, label: 'eyewhite',  swatch: '#f4ecd8' },
  { id:  2, label: 'accent',    swatch: '#3aa0ff' },
  { id:  3, label: 'tear',      swatch: '#5fb0ff' },
  { id:  4, label: 'glow_core', swatch: '#ffd680' },
  { id:  5, label: 'mouth',     swatch: '#8c4040' },
]

const EYE_GRID_W = 5      // dx ∈ [-2..+2]
const EYE_GRID_H = 5      // dy ∈ [-2..+2]
const MOUTH_GRID_W = 5    // dx ∈ [-2..+2]
const MOUTH_GRID_H = 3    // dy ∈ [-1..+1]

// (dx,dy) → cell index
const eyeIdx   = (dx: number, dy: number): number => (dy + 2) * EYE_GRID_W   + (dx + 2)
const eyeUv    = (cell: number): [number, number] => [
  (cell % EYE_GRID_W) - 2,
  Math.floor(cell / EYE_GRID_W) - 2,
]
const mouthIdx = (dx: number, dy: number): number => (dy + 1) * MOUTH_GRID_W + (dx + 2)
const mouthUv  = (cell: number): [number, number] => [
  (cell % MOUTH_GRID_W) - 2,
  Math.floor(cell / MOUTH_GRID_W) - 1,
]

interface EditableGrid {
  w: number
  h: number
  cells: Int8Array        // slot id per cell (-1 = clear)
  toUv: (cell: number) => [number, number]
}

function gridFromPreset(preset: FacePixelGrid, isEye: boolean): EditableGrid {
  const w = isEye ? EYE_GRID_W : MOUTH_GRID_W
  const h = isEye ? EYE_GRID_H : MOUTH_GRID_H
  const cells = new Int8Array(w * h).fill(-1)
  const toUv = isEye ? eyeUv : mouthUv
  const idx = isEye ? eyeIdx : mouthIdx
  for (const px of preset.pixels) {
    const slotId = SLOTS.find((s) => s.label === px.slot)?.id ?? 0
    const cellIdx = idx(px.dx, px.dy)
    if (cellIdx >= 0 && cellIdx < cells.length) {
      cells[cellIdx] = slotId as number
    }
  }
  return { w, h, cells, toUv }
}

function gridToPixels(grid: EditableGrid): FacePixel[] {
  const out: FacePixel[] = []
  for (let i = 0; i < grid.cells.length; i++) {
    const id = grid.cells[i]
    if (id < 0) continue
    const slot = SLOTS.find((s) => s.id === id)?.label
    if (slot === 'clear' || !slot) continue
    const [dx, dy] = grid.toUv(i)
    out.push({ dx, dy, slot: slot as FacePixelSlot })
  }
  return out
}

function clearChildren(el: HTMLElement) {
  while (el.firstChild) el.removeChild(el.firstChild)
}

export interface FacePixelEditorHandle {
  bakeAndUpload(): void
  refreshFromPresets(): void
}

/** Build the editor DOM. `host` is the parent element (e.g. div#face-pixel-editor).
 *  `onBake` receives the (styles, pixels) Int32Arrays formatted for outline.setFacePixelData. */
export function createFacePixelEditor(
  host: HTMLElement,
  onBake: (styles: Int32Array, pixels: Int32Array) => void,
): FacePixelEditorHandle {
  // Try to overlay any persisted edits onto the canonical presets BEFORE
  // building the editable grids. Falls through silently if nothing is
  // saved or the saved data shape doesn't match — preserves the existing
  // styles as the authoritative fallback.
  tryLoadFromStorage()

  // Per-style editable grids; clone from the (possibly restored) preset.
  const eyeGrids: EditableGrid[]   = EYE_STYLES.map((p)   => gridFromPreset(p, true))
  const mouthGrids: EditableGrid[] = MOUTH_STYLES.map((p) => gridFromPreset(p, false))
  let activeKind: 'eye' | 'mouth' = 'eye'
  let activeIdx = 0
  let activeSlot = 0   // pupil

  // -------- DOM build --------
  clearChildren(host)
  host.style.cssText = 'display:flex; flex-direction:column; gap:4px;'

  // Style picker row.
  const pickerRow = document.createElement('div')
  pickerRow.style.cssText = 'display:flex; gap:4px; align-items:center; flex-wrap:wrap;'
  const kindSel = document.createElement('select')
  kindSel.style.cssText = 'font-size:10px;'
  for (const k of ['eye', 'mouth']) {
    const o = document.createElement('option')
    o.value = k; o.textContent = k
    kindSel.appendChild(o)
  }
  pickerRow.appendChild(kindSel)
  const styleSel = document.createElement('select')
  styleSel.style.cssText = 'font-size:10px; flex:1;'
  pickerRow.appendChild(styleSel)
  host.appendChild(pickerRow)

  // Slot palette row (clickable swatches).
  const slotRow = document.createElement('div')
  slotRow.style.cssText = 'display:flex; gap:2px;'
  const slotButtons: HTMLButtonElement[] = []
  for (const s of SLOTS) {
    const b = document.createElement('button')
    b.title = s.label
    b.style.cssText =
      `width:14px; height:14px; padding:0; border:1px solid ${s.id === 0 ? '#fff' : '#445'};`
      + ` background:${s.swatch === 'transparent' ? '#222' : s.swatch};`
      + ` cursor:pointer; color:#888; font-size:9px;`
    if (s.swatch === 'transparent') b.textContent = '×'
    b.onclick = () => {
      activeSlot = s.id
      slotButtons.forEach((bb, i) => {
        bb.style.borderColor = SLOTS[i].id === activeSlot ? '#fff' : '#445'
      })
    }
    slotButtons.push(b)
    slotRow.appendChild(b)
  }
  host.appendChild(slotRow)

  // Grid canvas.
  const gridDiv = document.createElement('div')
  gridDiv.style.cssText = 'background:#111; padding:4px; border:1px solid #334; display:grid; gap:1px;'
  host.appendChild(gridDiv)

  // Bake row.
  const bakeRow = document.createElement('div')
  bakeRow.style.cssText = 'display:flex; gap:4px;'
  const bakeBtn = document.createElement('button')
  bakeBtn.textContent = 'bake'
  bakeBtn.style.fontSize = '10px'
  const resetBtn = document.createElement('button')
  resetBtn.textContent = 'reset'
  resetBtn.style.fontSize = '10px'
  bakeRow.appendChild(bakeBtn)
  bakeRow.appendChild(resetBtn)
  host.appendChild(bakeRow)

  function activeGrid(): EditableGrid {
    return activeKind === 'eye' ? eyeGrids[activeIdx] : mouthGrids[activeIdx]
  }

  function rebuildStyleSel() {
    clearChildren(styleSel)
    const list = activeKind === 'eye' ? EYE_STYLES : MOUTH_STYLES
    list.forEach((s, i) => {
      const o = document.createElement('option')
      o.value = String(i); o.textContent = `${i}: ${s.name}`
      styleSel.appendChild(o)
    })
    styleSel.value = String(activeIdx)
  }

  function renderGrid() {
    const g = activeGrid()
    clearChildren(gridDiv)
    gridDiv.style.gridTemplateColumns = `repeat(${g.w}, 14px)`
    for (let i = 0; i < g.cells.length; i++) {
      const cell = document.createElement('div')
      const slotId = g.cells[i]
      const slot = SLOTS.find((s) => s.id === slotId)
      cell.style.cssText =
        `width:14px; height:14px; cursor:pointer;`
        + ` background:${slot?.swatch === 'transparent' ? '#1a1a1a' : slot?.swatch ?? '#222'};`
      // Auto-bake on every click — pushes edits straight to the GPU so
      // the face on the character updates live as you paint, no extra
      // bake button press needed. Cost is a single uniform-buffer write
      // (~1.8KB) which is dwarfed by the per-frame raymarch.
      cell.onclick = () => {
        g.cells[i] = activeSlot
        renderGrid()
        bakeAndUpload()
      }
      cell.oncontextmenu = (e) => {
        e.preventDefault()
        g.cells[i] = -1
        renderGrid()
        bakeAndUpload()
      }
      gridDiv.appendChild(cell)
    }
  }

  function bakeAndUpload() {
    // Update the live preset arrays so subsequent reads (or external
    // serialization) pick up the edits.
    for (let i = 0; i < EYE_STYLES.length; i++) {
      EYE_STYLES[i] = { ...EYE_STYLES[i], pixels: gridToPixels(eyeGrids[i]) }
    }
    for (let i = 0; i < MOUTH_STYLES.length; i++) {
      MOUTH_STYLES[i] = { ...MOUTH_STYLES[i], pixels: gridToPixels(mouthGrids[i]) }
    }
    const allStyles = [...EYE_STYLES, ...MOUTH_STYLES]
    const flat: number[] = []
    const styles = new Int32Array(16 * 4)
    const slotIdMap: Record<string, number> = {
      pupil: 0, eyewhite: 1, accent: 2, tear: 3, glow_core: 4, mouth: 5,
    }
    for (let s = 0; s < allStyles.length; s++) {
      const start = flat.length / 4
      for (const px of allStyles[s].pixels) {
        const id = slotIdMap[px.slot] ?? 0
        flat.push(px.dx, px.dy, id, 0)
      }
      const count = flat.length / 4 - start
      styles[s * 4 + 0] = start
      styles[s * 4 + 1] = count
    }
    onBake(styles, new Int32Array(flat))
    saveToStorage()
  }

  function refreshFromPresets() {
    // Reset = restore canonical presets + drop any persisted edits.
    // The button is destructive; without clearing storage the next page
    // load would re-apply the saved (now-undesired) edits.
    for (let i = 0; i < EYE_STYLES.length; i++)   EYE_STYLES[i]   = cloneGrid(ORIGINAL_EYE_STYLES[i])
    for (let i = 0; i < MOUTH_STYLES.length; i++) MOUTH_STYLES[i] = cloneGrid(ORIGINAL_MOUTH_STYLES[i])
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
    EYE_STYLES.forEach((p, i)   => { eyeGrids[i]   = gridFromPreset(p, true) })
    MOUTH_STYLES.forEach((p, i) => { mouthGrids[i] = gridFromPreset(p, false) })
    renderGrid()
    bakeAndUpload()
  }

  kindSel.onchange = () => {
    activeKind = kindSel.value as 'eye' | 'mouth'
    activeIdx = 0
    rebuildStyleSel()
    renderGrid()
  }
  styleSel.onchange = () => {
    activeIdx = parseInt(styleSel.value, 10) || 0
    renderGrid()
  }
  bakeBtn.onclick = bakeAndUpload
  resetBtn.onclick = refreshFromPresets

  rebuildStyleSel()
  renderGrid()
  bakeAndUpload()

  return { bakeAndUpload, refreshFromPresets }
}
