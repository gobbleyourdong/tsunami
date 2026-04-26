/**
 * SDF Modeler — VL-driven live viewer over the ark raymarch renderer.
 *
 * Loads ark.json files emitted by sdf_modeling_research/compiler/ark_emit.py,
 * uploads them to the WebGPU raymarcher, and re-renders on change. The
 * polling loop fetches a fixed inbox path so an external VL agent can drive
 * the view by writing to one file — every write is visible within ~250ms.
 *
 * Intentionally DOES NOT touch skeleton_demo.* — separate demo, separate file.
 *
 * Spec input shape (matches ark_emit.py output):
 *   {
 *     name, archetype, scale_meters,
 *     palette_table: { name → slot:int },
 *     palette_rgb:   [[r,g,b], ...]   // slot-indexed
 *     primitives: [{
 *       type:int (0..12), params:[4]f32, centerWorld:[3]f32,
 *       rotation:[4]f32 (xyzw), paletteSlot:int, paletteSlotB:int,
 *       colorFunc:int (0..8), colorExtent:f32,
 *       blendGroup:int, blendRadius:f32, flags:int
 *     }, ...]
 *   }
 *
 * Bone model: every primitive uses bone 0, identity transform. centerWorld
 * lands directly into RaymarchPrimitive.offsetInBone — same numerical effect
 * as a translation since boneWorld = I.
 */

import { initGPU } from '../src/renderer/gpu'
import { Camera } from '../src/renderer/camera'
import { FrameLoop } from '../src/renderer/frame'
import { mat4 } from '../src/math/vec'
import {
  createRaymarchRenderer,
  type RaymarchPrimitive,
  type VATData,
  type FaceMark,
} from '../src/character3d/raymarch_renderer'

interface ArkSpec {
  name: string
  archetype: string
  scale_meters: number
  palette_table: Record<string, number>
  palette_rgb?: Array<[number, number, number]>
  primitives: ArkPrim[]
  primitive_count?: number
  warnings?: string[]
  // iter 53/54 — F260: bone-attached color-overrides (eyes / mouth / scars).
  // Renderer caps at 16. shape ∈ {circle, rect, line}.
  face_marks?: ArkFaceMark[]
}
interface ArkFaceMark {
  shape: 'circle' | 'rect' | 'line'
  boneIdx: number
  paletteSlot: number
  localCenter: [number, number, number]
  localNormal: [number, number, number]
  size: [number, number]
}
interface ArkPrim {
  type: number
  params: [number, number, number, number]
  centerWorld: [number, number, number]
  rotation: [number, number, number, number]
  paletteSlot: number
  paletteSlotB: number
  colorFunc: number
  colorExtent: number
  blendGroup: number
  blendRadius: number
  flags: number
  _id?: string
  _type_str?: string
}

const POLL_MS = 250
const DEFAULT_POLL_PATH = '/sdf_modeler/inbox.ark.json'
const QUICK_LIST_PATH = '/sdf_modeler/index.json'

// Tiny DOM helper — avoids innerHTML so any user-supplied / fetched string
// (spec name, file name, archetype) can't smuggle HTML into the page.
function el(tag: string, opts: { class?: string; text?: string; title?: string; style?: Record<string,string>; children?: Node[] } = {}) {
  const n = document.createElement(tag)
  if (opts.class) n.className = opts.class
  if (opts.text != null) n.textContent = opts.text
  if (opts.title) n.title = opts.title
  if (opts.style) for (const k in opts.style) (n.style as any)[k] = opts.style[k]
  if (opts.children) for (const c of opts.children) n.appendChild(c)
  return n
}
function clear(node: Element) {
  while (node.firstChild) node.removeChild(node.firstChild)
}

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const statusEl = document.getElementById('status-banner')!
  const errorEl = document.getElementById('error')!

  function fitCanvas() {
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    canvas.width  = Math.floor(canvas.clientWidth  * dpr)
    canvas.height = Math.floor(canvas.clientHeight * dpr)
  }
  fitCanvas()

  let gpu
  try {
    gpu = await initGPU(canvas)
  } catch (e) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU init failed: ${(e as Error).message}\n\nThis demo needs a Chrome/Edge build with WebGPU enabled.`
    return
  }
  const { device, format, context } = gpu

  // Minimal VAT: 1 frame × 1 joint, identity matrix. Every prim points to
  // bone 0 so the bone transform is a no-op and offsetInBone IS world space.
  const vatData = new Float32Array(16)
  mat4.identity(vatData)
  const vatBuffer = device.createBuffer({
    label: 'sdf-modeler-vat',
    size: vatData.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(vatBuffer, 0, vatData)
  const vat: VATData = { buffer: vatBuffer, numInstances: 1, numFrames: 1 }

  const MAX_PALETTE_SLOTS = 32
  const initialPalette = new Float32Array(MAX_PALETTE_SLOTS * 4)
  for (let i = 0; i < MAX_PALETTE_SLOTS; i++) {
    initialPalette[i * 4 + 0] = 0.4
    initialPalette[i * 4 + 1] = 0.4
    initialPalette[i * 4 + 2] = 0.45
    initialPalette[i * 4 + 3] = 1.0
  }

  const initialPrims: RaymarchPrimitive[] = [{
    type: 0, paletteSlot: 0, boneIdx: 0,
    params: [0.0001, 0, 0, 0],
    offsetInBone: [0, -1000, 0],
  }]

  const raymarch = createRaymarchRenderer(device, format, initialPrims, initialPalette, vat, { maxSteps: 64 })

  // MRT throwaway textures. Raymarch writes 3 attachments; only color
  // (palette tint) lands on the swap chain. Normal+depthViz are discarded.
  let normalTex: GPUTexture | null = null
  let depthTex: GPUTexture | null = null
  let depthStencilTex: GPUTexture | null = null
  let normalView: GPUTextureView | null = null
  let depthView: GPUTextureView | null = null
  let depthStencilView: GPUTextureView | null = null
  let lastCanvasW = 0, lastCanvasH = 0

  function ensureMRT(w: number, h: number) {
    if (w === lastCanvasW && h === lastCanvasH && normalTex) return
    normalTex?.destroy(); depthTex?.destroy(); depthStencilTex?.destroy()
    const usage = GPUTextureUsage.RENDER_ATTACHMENT
    normalTex       = device.createTexture({ label: 'sdf-modeler-normal',       size: [w, h], format, usage })
    depthTex        = device.createTexture({ label: 'sdf-modeler-depthviz',     size: [w, h], format, usage })
    depthStencilTex = device.createTexture({ label: 'sdf-modeler-depthstencil', size: [w, h], format: 'depth24plus-stencil8', usage })
    normalView       = normalTex.createView()
    depthView        = depthTex.createView()
    depthStencilView = depthStencilTex.createView()
    lastCanvasW = w; lastCanvasH = h
  }

  // --- Camera + orbit -----------------------------------------------------
  const camera = new Camera({
    mode: 'perspective',
    fov: 35, near: 0.01, far: 50,
    position: [0.6, 0.5, 1.4],
    target: [0, 0.15, 0],
    controls: 'orbit',
  })
  camera.setAspect(canvas.width, canvas.height)
  camera.update()

  let autoOrbit = true
  let dragLastX = 0, dragLastY = 0, dragging = false
  canvas.addEventListener('mousedown', (e) => {
    dragging = true; dragLastX = e.clientX; dragLastY = e.clientY
    autoOrbit = false; setSpinUI()
  })
  window.addEventListener('mouseup', () => { dragging = false })
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return
    const dx = e.clientX - dragLastX, dy = e.clientY - dragLastY
    dragLastX = e.clientX; dragLastY = e.clientY
    camera.orbitRotate(-dx * 0.01, -dy * 0.01)
  })
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault()
    camera.orbitZoom(1 + e.deltaY * 0.001)
  }, { passive: false })
  canvas.addEventListener('dblclick', () => setView('iso'))

  function setView(name: 'iso'|'front'|'side'|'top') {
    const dist = (camera as any).orbitDistance as number
    const t = camera.target
    const presets: Record<string, [number,number,number]> = {
      iso:   [t[0]+dist*0.5, t[1]+dist*0.4, t[2]+dist*0.7],
      front: [t[0],          t[1],          t[2]+dist],
      side:  [t[0]+dist,     t[1],          t[2]],
      top:   [t[0],          t[1]+dist,     t[2]+0.001],
    }
    camera.position = presets[name]
    const dx = camera.position[0] - t[0]
    const dy = camera.position[1] - t[1]
    const dz = camera.position[2] - t[2]
    const d = Math.sqrt(dx*dx + dy*dy + dz*dz)
    ;(camera as any).orbitDistance = d
    ;(camera as any).orbitYaw = Math.atan2(dx, dz)
    ;(camera as any).orbitPitch = Math.asin(dy / d)
  }

  // --- Spec apply ---------------------------------------------------------
  let currentPrimCount = 0
  let currentMarkCount = 0

  function fitCameraToSpec(spec: ArkSpec) {
    if (!spec.primitives.length) return
    let minX = Infinity, minY = Infinity, minZ = Infinity
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
    for (const p of spec.primitives) {
      const c = p.centerWorld
      const r = Math.max(Math.abs(p.params[0]), Math.abs(p.params[1]), Math.abs(p.params[2]), 0.01)
      minX = Math.min(minX, c[0] - r); maxX = Math.max(maxX, c[0] + r)
      minY = Math.min(minY, c[1] - r); maxY = Math.max(maxY, c[1] + r)
      minZ = Math.min(minZ, c[2] - r); maxZ = Math.max(maxZ, c[2] + r)
    }
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2
    const ext = Math.max(maxX - minX, maxY - minY, maxZ - minZ)
    camera.target = [cx, cy, cz]
    ;(camera as any).orbitDistance = Math.max(0.3, ext * 1.8)
  }

  function applySpec(spec: ArkSpec, source: string) {
    const rgb = spec.palette_rgb ?? []
    for (let i = 0; i < Math.min(rgb.length, MAX_PALETTE_SLOTS); i++) {
      const [r, g, b] = rgb[i]
      raymarch.setPaletteSlot(i, r, g, b, 1)
    }
    const prims: RaymarchPrimitive[] = spec.primitives.map((p) => ({
      type: p.type,
      paletteSlot: p.paletteSlot,
      boneIdx: 0,
      params: [p.params[0], p.params[1], p.params[2], p.params[3]],
      offsetInBone: [p.centerWorld[0], p.centerWorld[1], p.centerWorld[2]],
      colorFunc: (p.colorFunc ?? 0) as any,
      paletteSlotB: p.paletteSlotB ?? p.paletteSlot,
      colorExtent: p.colorExtent ?? 0.1,
      blendGroup: p.blendGroup ?? 0,
      blendRadius: p.blendRadius ?? 0,
      rotation: [p.rotation[0], p.rotation[1], p.rotation[2], p.rotation[3]],
      shiny: !!(p.flags & 0x80),
      unlit: !!(p.flags & 0x40),
    }))
    raymarch.setPrimitives(prims)
    currentPrimCount = prims.length
    // iter 54 — F265: face_marks pass-through. Renderer caps at 16.
    // Always call setFaceMarks (even with empty array) so a spec WITHOUT
    // face_marks clears any marks from the previous spec.
    const marksIn = spec.face_marks ?? []
    const marks: FaceMark[] = marksIn.slice(0, 16).map((m) => ({
      shape: m.shape,
      boneIdx: m.boneIdx ?? 0,
      paletteSlot: m.paletteSlot,
      localCenter: [m.localCenter[0], m.localCenter[1], m.localCenter[2]],
      localNormal: [m.localNormal[0], m.localNormal[1], m.localNormal[2]],
      size: [m.size[0], m.size[1]],
    }))
    raymarch.setFaceMarks(marks)
    currentMarkCount = marks.length
    fitCameraToSpec(spec)
    renderPaletteStrip(spec)
    renderSpecMeta(spec, source)
    statusEl.textContent = `applied "${spec.name}" · ${prims.length} prims · ${marks.length} marks · ${source}`
    statusEl.className = 'fresh'
  }

  function showError(msg: string) {
    statusEl.textContent = `error: ${msg}`
    statusEl.className = 'error'
  }

  function renderPaletteStrip(spec: ArkSpec) {
    const strip = document.getElementById('palette-strip')!
    clear(strip)
    const rgb = spec.palette_rgb ?? []
    const names = Object.keys(spec.palette_table ?? {})
    for (let i = 0; i < rgb.length; i++) {
      const [r, g, b] = rgb[i]
      const sw = el('div', {
        class: 'swatch',
        title: `${i}: ${names[i] ?? '<unnamed>'} (${r.toFixed(2)},${g.toFixed(2)},${b.toFixed(2)})`,
        style: { background: `rgb(${Math.round(r*255)},${Math.round(g*255)},${Math.round(b*255)})` },
      })
      strip.appendChild(sw)
    }
  }
  function renderSpecMeta(spec: ArkSpec, source: string) {
    const root = document.getElementById('spec-meta')!
    clear(root)
    const wn = (spec.warnings ?? []).length
    const line1 = el('div', { children: [
      el('strong', { text: spec.name }),
      el('span', { text: ' ' }),
      el('span', { class: 'pill', text: spec.archetype }),
    ]})
    const line2 = el('div', {
      text: `scale ${spec.scale_meters?.toFixed?.(2) ?? '?'}m · ${spec.primitives.length} prims · ${wn} warnings`,
    })
    const line3 = el('div', {
      text: `source: ${source}`,
      style: { color: '#6a7585', marginTop: '2px' },
    })
    root.appendChild(line1); root.appendChild(line2); root.appendChild(line3)
  }

  async function loadQuickList() {
    const listEl = document.getElementById('spec-list')!
    try {
      const r = await fetch(QUICK_LIST_PATH)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const list: Array<{file:string;name:string;archetype:string;prim_count:number;warnings:number}> = await r.json()
      list.sort((a, b) => (a.warnings - b.warnings) || a.archetype.localeCompare(b.archetype) || a.name.localeCompare(b.name))
      clear(listEl)
      for (const item of list) {
        const left = el('span', { text: item.name })
        const right = el('span', {
          class: 'meta',
          text: `${item.archetype} · ${item.prim_count}p${item.warnings ? ' · '+item.warnings+'w' : ''}`,
        })
        const row = el('div', {
          class: 'spec-item' + (item.warnings > 0 ? ' warn' : ''),
          children: [left, right],
        })
        ;(row as HTMLElement).onclick = () => loadFromPath(`/sdf_modeler/${item.file}`)
        listEl.appendChild(row)
      }
    } catch (e) {
      listEl.textContent = `(no index.json — ${(e as Error).message})`
    }
  }
  async function loadFromPath(path: string) {
    try {
      const r = await fetch(path, { cache: 'no-cache' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const spec = await r.json()
      applySpec(spec, path)
    } catch (e) {
      showError((e as Error).message)
    }
  }

  // --- Polling ------------------------------------------------------------
  let pollOn = true
  let pollPath = DEFAULT_POLL_PATH
  let lastEtag: string | null = null
  let lastBody: string | null = null

  async function pollOnce() {
    const pollStat = document.getElementById('poll-status')!
    try {
      const r = await fetch(pollPath, { cache: 'no-cache' })
      if (!r.ok) {
        pollStat.textContent = `404 (waiting…)`
        return
      }
      const etag = r.headers.get('ETag') ?? r.headers.get('Last-Modified')
      const body = await r.text()
      if (etag && etag === lastEtag) {
        pollStat.textContent = `idle · ${new Date().toLocaleTimeString()}`
        return
      }
      if (!etag && body === lastBody) {
        pollStat.textContent = `idle · ${new Date().toLocaleTimeString()}`
        return
      }
      lastEtag = etag
      lastBody = body
      const spec = JSON.parse(body)
      applySpec(spec, `poll ${pollPath}`)
      pollStat.textContent = `applied @ ${new Date().toLocaleTimeString()}`
    } catch (e) {
      pollStat.textContent = `err: ${(e as Error).message}`
    }
  }
  let pollTimer: number | null = null
  function setPolling(on: boolean) {
    pollOn = on
    const btn = document.getElementById('poll-toggle') as HTMLButtonElement
    btn.textContent = on ? 'ON' : 'OFF'
    btn.className = on ? 'on' : 'off'
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    if (on) {
      pollOnce()
      pollTimer = window.setInterval(pollOnce, POLL_MS)
    }
  }
  function setSpinUI() {
    const btn = document.getElementById('spin-toggle') as HTMLButtonElement
    btn.textContent = autoOrbit ? 'auto-orbit' : 'paused'
    btn.className = autoOrbit ? 'on' : 'off'
  }

  // --- UI bindings --------------------------------------------------------
  ;(document.getElementById('poll-toggle') as HTMLButtonElement).onclick = () => setPolling(!pollOn)
  ;(document.getElementById('poll-path') as HTMLInputElement).addEventListener('change', (e) => {
    pollPath = (e.target as HTMLInputElement).value.trim() || DEFAULT_POLL_PATH
    lastEtag = null; lastBody = null
    if (pollOn) { setPolling(false); setPolling(true) }
  })
  ;(document.getElementById('manual-load') as HTMLButtonElement).onclick = () => {
    const v = (document.getElementById('manual-path') as HTMLInputElement).value.trim()
    if (v) loadFromPath(v)
  }
  ;(document.getElementById('manual-apply') as HTMLButtonElement).onclick = () => {
    const v = (document.getElementById('manual-text') as HTMLTextAreaElement).value
    try { applySpec(JSON.parse(v), 'paste') } catch (e) { showError((e as Error).message) }
  }
  ;(document.getElementById('manual-file') as HTMLButtonElement).onclick = () => {
    (document.getElementById('manual-file-input') as HTMLInputElement).click()
  }
  ;(document.getElementById('manual-file-input') as HTMLInputElement).addEventListener('change', async (e) => {
    const f = (e.target as HTMLInputElement).files?.[0]
    if (!f) return
    const txt = await f.text()
    try { applySpec(JSON.parse(txt), `file:${f.name}`) } catch (err) { showError((err as Error).message) }
    ;(document.getElementById('manual-text') as HTMLTextAreaElement).value = txt
  })
  ;(document.getElementById('spin-toggle') as HTMLButtonElement).onclick = () => {
    autoOrbit = !autoOrbit
    setSpinUI()
  }
  document.querySelectorAll('button[data-view]').forEach((btn) => {
    (btn as HTMLButtonElement).onclick = () => setView(btn.getAttribute('data-view') as any)
  })

  loadQuickList()
  setPolling(true)
  setSpinUI()

  // --- Render loop --------------------------------------------------------
  let frameIdx = 0
  const loop = new FrameLoop()
  loop.onRender = (stats) => {
    const w = canvas.clientWidth, h = canvas.clientHeight
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const tw = Math.floor(w * dpr), th = Math.floor(h * dpr)
    if (tw !== canvas.width || th !== canvas.height) {
      canvas.width = tw; canvas.height = th
      camera.setAspect(tw, th)
    }
    ensureMRT(canvas.width, canvas.height)

    if (autoOrbit) camera.orbitRotate(0.004, 0)
    camera.update()
    raymarch.setTime(stats.elapsed)

    const encoder = device.createCommandEncoder({ label: 'sdf-modeler-encoder' })
    const swap = context.getCurrentTexture().createView()
    const pass = encoder.beginRenderPass({
      label: 'sdf-modeler-pass',
      colorAttachments: [
        { view: swap,        loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.024, g: 0.031, b: 0.063, a: 1 } },
        { view: normalView!, loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1.0, a: 0 } },
        { view: depthView!,  loadOp: 'clear', storeOp: 'store', clearValue: { r: 1, g: 0, b: 0, a: 0 } },
      ],
      depthStencilAttachment: {
        view: depthStencilView!,
        depthLoadOp: 'clear', depthStoreOp: 'store', depthClearValue: 1.0,
        stencilLoadOp: 'clear', stencilStoreOp: 'store', stencilClearValue: 0,
      },
    })
    raymarch.draw(
      pass,
      camera.view,
      camera.projection,
      [camera.position[0], camera.position[1], camera.position[2]],
      frameIdx,
    )
    pass.end()
    device.queue.submit([encoder.finish()])
    frameIdx++

    statsEl.textContent = `${stats.fps.toFixed(0)} fps · ${currentPrimCount} prims · ${currentMarkCount} marks · ${canvas.width}×${canvas.height}`
  }
  loop.start()
}

main().catch((e) => {
  console.error(e)
  const errorEl = document.getElementById('error')
  if (errorEl) {
    errorEl.style.display = 'block'
    errorEl.textContent = `Fatal: ${(e as Error).message}`
  }
})
