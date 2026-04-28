/**
 * Creature Demo — minimal procedural-rig viewer.
 *
 * One central segmented ribbon, head at one end, optional mirrored
 * limb pairs along the body. Static T-pose for now; animation layers
 * on later. Preset buttons cycle through bird / spider / snake /
 * centipede silhouettes built from the same generator.
 *
 * Renderer setup mirrors skeleton_demo's MRT + outline + raymarch-cache
 * pattern, but stripped to the minimum needed for a static rig — no
 * VAT animation, no character spec parser, no anim dropdown.
 */

import { initGPU, Camera, FrameLoop } from '../src'
import { createRaymarchRenderer, expandMirrors, type RaymarchPrimitive } from '../src/character3d/raymarch_renderer'
import { createOutlinePass } from '../src/character3d/outline'
import {
  buildCreature,
  CREATURE_PRESETS,
  type CreatureSpec,
} from '../src/character3d/creature_rig'

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const gpu = await initGPU(canvas)
  const { device, format } = gpu
  const SCENE_FORMAT: GPUTextureFormat = 'rgba8unorm'

  // ---------- Palette ----------
  // 32 slots × RGBA. Just enough for skin / fur / feather / leather.
  // Slot indices match what creature_rig.ts emits (2/8/9/10).
  const palette = new Float32Array(32 * 4)
  const setSlot = (s: number, r: number, g: number, b: number) => {
    palette[s * 4 + 0] = r; palette[s * 4 + 1] = g; palette[s * 4 + 2] = b; palette[s * 4 + 3] = 1
  }
  setSlot(0,  0,    0,    0   )    // bg
  setSlot(2,  0.95, 0.75, 0.6 )    // skin
  setSlot(8,  0.45, 0.30, 0.18)    // fur (warm brown)
  setSlot(9,  0.55, 0.55, 0.65)    // feather (cool grey)
  setSlot(10, 0.30, 0.20, 0.10)    // leather (dark)

  // ---------- MRT targets ----------
  const targets = {
    sceneTex: null as GPUTexture | null,
    normalTex: null as GPUTexture | null,
    depthVizTex: null as GPUTexture | null,
    sceneDepth: null as GPUTexture | null,
    sceneView: null as GPUTextureView | null,
    normalView: null as GPUTextureView | null,
    depthVizView: null as GPUTextureView | null,
    sceneDepthView: null as GPUTextureView | null,
  }
  const makeTarget = (label: string, w: number, h: number) => device.createTexture({
    label, size: { width: w, height: h }, format: SCENE_FORMAT,
    usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
  })
  const recreateTargets = (w: number, h: number) => {
    targets.sceneTex?.destroy(); targets.normalTex?.destroy()
    targets.depthVizTex?.destroy(); targets.sceneDepth?.destroy()
    targets.sceneTex = makeTarget('cd-scene', w, h)
    targets.normalTex = makeTarget('cd-normal', w, h)
    targets.depthVizTex = makeTarget('cd-depth-viz', w, h)
    targets.sceneDepth = device.createTexture({
      label: 'cd-scene-depth', size: { width: w, height: h },
      format: 'depth24plus-stencil8', usage: GPUTextureUsage.RENDER_ATTACHMENT,
    })
    targets.sceneView = targets.sceneTex.createView()
    targets.normalView = targets.normalTex.createView()
    targets.depthVizView = targets.depthVizTex.createView()
    targets.sceneDepthView = targets.sceneDepth.createView()
  }
  recreateTargets(canvas.width, canvas.height)

  // ---------- VAT-shaped buffer for the static rig ----------
  // The raymarch renderer reads bone matrices from a GPU buffer using
  // (frameIdx * numJoints + boneIdx) * 16 floats. For a static rig we
  // allocate numFrames=1 and write the bind-pose matrices once.
  let currentSpec: CreatureSpec = CREATURE_PRESETS.bird
  let built = buildCreature(currentSpec)
  let bonesBuffer = device.createBuffer({
    label: 'creature-bones',
    size: built.worldMats.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(bonesBuffer, 0, built.worldMats)

  // ---------- Raymarch renderer ----------
  const initialPrims = expandMirrors(built.prims as RaymarchPrimitive[])
  const raymarch = createRaymarchRenderer(
    device, SCENE_FORMAT,
    initialPrims, palette,
    { buffer: bonesBuffer, numInstances: built.rig.length, numFrames: 1 },
    { maxSteps: 96 },
  )
  raymarch.resizeCache(canvas.width, canvas.height)
  raymarch.setBgMode('transparent')

  // ---------- Outline pass ----------
  const outline = createOutlinePass(
    device, format,
    targets.sceneView!, targets.normalView!, targets.depthVizView!,
    canvas.width, canvas.height,
  )

  // ---------- Camera ----------
  // Orbit around origin. Ortho projection sized to fit ~1m creature.
  const camera = new Camera()
  camera.orthoSize = 0.8
  camera.aspect = canvas.width / canvas.height
  let yaw = 0.4, pitch = 0.25
  let zoom = 0.8
  const updateCamera = () => {
    const r = 2.0
    const cx = Math.cos(pitch) * Math.sin(yaw) * r
    const cy = Math.sin(pitch) * r
    const cz = Math.cos(pitch) * Math.cos(yaw) * r
    camera.lookAt([cx, cy, cz], [0, 0.1, 0], [0, 1, 0])
    camera.orthoSize = zoom
    camera.updateProjection()
  }
  updateCamera()

  // Drag to orbit, wheel to zoom.
  let dragging = false
  let dragX = 0, dragY = 0
  canvas.addEventListener('pointerdown', (e) => { dragging = true; dragX = e.clientX; dragY = e.clientY })
  window.addEventListener('pointerup',   () => { dragging = false })
  window.addEventListener('pointermove', (e) => {
    if (!dragging) return
    yaw   -= (e.clientX - dragX) * 0.005
    pitch += (e.clientY - dragY) * 0.005
    pitch = Math.max(-Math.PI * 0.45, Math.min(Math.PI * 0.45, pitch))
    dragX = e.clientX; dragY = e.clientY
    updateCamera()
  })
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault()
    zoom *= e.deltaY > 0 ? 1.1 : 0.9
    zoom = Math.max(0.2, Math.min(3.0, zoom))
    updateCamera()
  })

  // ---------- Stats / preset / dial DOM ----------
  const statsEl = document.getElementById('stats') as HTMLDivElement
  const presetsEl = document.getElementById('presets') as HTMLDivElement
  const dialsEl = document.getElementById('dials') as HTMLDivElement

  // ---------- Rebuild creature on preset change ----------
  function applySpec(spec: CreatureSpec) {
    currentSpec = spec
    built = buildCreature(spec)
    // Bones buffer: reallocate if the joint count grew, otherwise just
    // overwrite the existing storage.
    const neededBytes = built.worldMats.byteLength
    if (bonesBuffer.size < neededBytes) {
      bonesBuffer.destroy()
      bonesBuffer = device.createBuffer({
        label: 'creature-bones',
        size: neededBytes,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      })
      raymarch.rebind({ buffer: bonesBuffer, numInstances: built.rig.length, numFrames: 1 })
    }
    device.queue.writeBuffer(bonesBuffer, 0, built.worldMats)
    raymarch.setPrimitives(expandMirrors(built.prims as RaymarchPrimitive[]))
    statsEl.textContent = `${spec.name}\n${built.rig.length} joints\n${built.prims.length} prims`
  }

  // ---------- UI buttons + dials ----------
  for (const name of Object.keys(CREATURE_PRESETS)) {
    const btn = document.createElement('button')
    btn.textContent = name
    btn.onclick = () => {
      applySpec(CREATURE_PRESETS[name])
      for (const sib of presetsEl.querySelectorAll('button')) sib.classList.remove('active')
      btn.classList.add('active')
    }
    presetsEl.appendChild(btn)
  }
  ;(presetsEl.querySelector('button') as HTMLButtonElement | null)?.classList.add('active')

  // Body-segment slider — overrides currentSpec.body.segments live.
  const segRow = document.createElement('label')
  const segLabel = document.createElement('span')
  segLabel.style.width = '60px'
  segLabel.textContent = 'segments'
  const segRange = document.createElement('input')
  segRange.type = 'range'
  segRange.min = '0'
  segRange.max = '30'
  segRange.step = '1'
  const segVal = document.createElement('span')
  segVal.className = 'val'
  segRow.append(segLabel, segRange, segVal)
  dialsEl.appendChild(segRow)
  segRange.value = String(currentSpec.body.segments)
  segVal.textContent = String(currentSpec.body.segments)
  segRange.oninput = () => {
    const n = parseInt(segRange.value, 10)
    segVal.textContent = String(n)
    applySpec({ ...currentSpec, body: { ...currentSpec.body, segments: n } })
  }

  applySpec(currentSpec)

  // ---------- Render loop ----------
  const loop = new FrameLoop()
  loop.onRender = (stats) => {
    void stats
    const encoder = device.createCommandEncoder({ label: 'cd-encoder' })

    // Raymarch: render into the cache framebuffer (orthonormal pass).
    const eye: [number, number, number] = [
      camera.view[12], camera.view[13], camera.view[14],
    ]
    const pxPerM = canvas.height / (2 * camera.orthoSize)
    raymarch.setTime(performance.now() * 0.001)
    raymarch.setPxPerM(pxPerM)
    raymarch.marchIntoCache(encoder, camera.view, camera.projection, eye, 0)

    // Pass 1: blit raymarch cache into MRT scene targets.
    const scenePass = encoder.beginRenderPass({
      colorAttachments: [
        { view: targets.sceneView!,    loadOp: 'clear', storeOp: 'store', clearValue: { r: 0,   g: 0,   b: 0,   a: 0 } },
        { view: targets.normalView!,   loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1.0, a: 0 } },
        { view: targets.depthVizView!, loadOp: 'clear', storeOp: 'store', clearValue: { r: 1,   g: 0,   b: 0,   a: 0 } },
      ],
      depthStencilAttachment: {
        view: targets.sceneDepthView!,
        depthLoadOp: 'clear', depthStoreOp: 'store', depthClearValue: 1.0,
        stencilLoadOp: 'clear', stencilStoreOp: 'store', stencilClearValue: 0,
      },
    })
    raymarch.blitCacheToPass(scenePass)
    scenePass.end()

    // Pass 2: outline reads sceneTex → writes canvas with NAVY ring.
    const canvasView = gpu.context.getCurrentTexture().createView()
    outline.run(encoder, canvasView)

    device.queue.submit([encoder.finish()])
  }
  loop.start()
}

main().catch((err) => {
  console.error(err)
  const e = document.getElementById('error') as HTMLDivElement
  if (e) {
    e.style.display = 'block'
    e.textContent = String(err)
  }
})
