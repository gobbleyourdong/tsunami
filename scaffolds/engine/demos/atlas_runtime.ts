/**
 * Atlas Runtime Consumer — the game-engine side of the pipeline.
 *
 * Sequence:
 *   1. Load Mixamo JSON → bake skeleton VAT → render all (view, frame)
 *      cells into an offscreen RGBA8 atlas texture in G-BUFFER MODE
 *      (R=palette idx, G,B=normal.xy, A=depth).
 *   2. Display pass uses a second shader that samples the atlas, decodes
 *      the G-buffer per-pixel, looks up color via the palette LUT, and
 *      applies scene lighting with a user-controlled light direction.
 *   3. UI: view picker, light direction sliders, clickable palette swatches
 *      that live-edit the palette texture. Every change shows instantly.
 *
 * Proof: the 3D rig + VAT are UNUSED at display time. The display shader
 * only knows about (atlas, palette, light). That's the shipping contract.
 */

import { initGPU, FrameLoop } from '../src'
import { mat4 } from '../src/math/vec'
import { bakeSkeletonVAT } from '../src/character3d/skeleton'
import { createSkeletonRenderer } from '../src/character3d/skeleton_renderer'
import { loadMixamoBake, chibiBoneDisplayMats, chibiMaterial } from '../src/character3d/mixamo_loader'

const NUM_VIEWS = 8
const CELL_SIZE = 128
const ATLAS_W = NUM_VIEWS * CELL_SIZE       // 1024
const VAT_FRAMES = 60
const ATLAS_H = VAT_FRAMES * CELL_SIZE      // 7680

const VIEW_LABELS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

function buildViewMatrices(): { view: Float32Array; proj: Float32Array }[] {
  const out: { view: Float32Array; proj: Float32Array }[] = []
  const pitch = Math.atan(1 / Math.sqrt(2))
  const distance = 4
  const target: [number, number, number] = [0, 0.9, 0]
  const up: [number, number, number] = [0, 1, 0]
  const orthoSize = 1.3
  for (let i = 0; i < NUM_VIEWS; i++) {
    const yaw = (i / NUM_VIEWS) * Math.PI * 2
    const pos: [number, number, number] = [
      target[0] + distance * Math.cos(pitch) * Math.sin(yaw),
      target[1] + distance * Math.sin(pitch),
      target[2] + distance * Math.cos(pitch) * Math.cos(yaw),
    ]
    const view = mat4.create()
    mat4.lookAt(view, pos, target, up)
    const proj = mat4.create()
    mat4.ortho(proj, -orthoSize, orthoSize, -orthoSize, orthoSize, 0.1, 50)
    out.push({ view, proj })
  }
  return out
}

// --- G-buffer consumer shader ---
//   Full-screen quad-ish (actually a specific cell-sized blit) that:
//   - samples atlas at the current (view, frame) cell
//   - decodes R=palette idx, GB=normal.xy, A=depth
//   - reconstructs normal.z = sqrt(1 - nx² - ny²)
//   - looks up palette[slot]
//   - Lambert-lights with user light direction
//   - writes out final RGBA (or discards transparent pixels).
const CONSUMER_SHADER = /* wgsl */ `
struct U {
  // Cell location in atlas, normalized [0,1]: u0, v0, duv (width/height fraction).
  uv0: vec2f,
  uvSize: vec2f,
  lightDir: vec3f,
  _pad0: f32,
}

@group(0) @binding(0) var<uniform> u: U;
@group(0) @binding(1) var atlasTex: texture_2d<f32>;
@group(0) @binding(2) var atlasSamp: sampler;
@group(0) @binding(3) var<storage, read> palette: array<vec4f>;

struct VsOut {
  @builtin(position) position: vec4f,
  @location(0) localUv: vec2f,
}

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  // Fullscreen triangle covering NDC [-1, +3]² (standard trick).
  let c = vec2f(f32((vid << 1u) & 2u), f32(vid & 2u));
  var out: VsOut;
  out.position = vec4f(c * 2.0 - 1.0, 0.0, 1.0);
  out.localUv = vec2f(c.x, 1.0 - c.y);   // flip Y for texture coords
  return out;
}

@fragment
fn fs_main(@location(0) localUv: vec2f) -> @location(0) vec4f {
  let atlasUv = u.uv0 + localUv * u.uvSize;
  let gbuf = textureSample(atlasTex, atlasSamp, atlasUv);

  // Decode G-buffer.
  let slot = u32(round(gbuf.r * 255.0));
  let nx = gbuf.g * 2.0 - 1.0;
  let ny = gbuf.b * 2.0 - 1.0;
  let nz = sqrt(max(0.0, 1.0 - nx * nx - ny * ny));
  let normal = vec3f(nx, ny, nz);
  let depth = gbuf.a;

  // Background pixels: slot 0 = bg (transparent) — the sprite's silhouette.
  if (slot == 0u || depth >= 0.999) {
    discard;
  }

  // LUT lookup + Lambert lighting.
  let baseColor = palette[slot].rgb;
  let light = normalize(u.lightDir);
  let lambert = max(dot(normal, light), 0.0);
  let shade = lambert * 0.75 + 0.25;
  return vec4f(baseColor * shade, 1.0);
}
`

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const errorEl = document.getElementById('error')!
  const lightThetaEl = document.getElementById('lightTheta') as HTMLInputElement
  const lightPhiEl = document.getElementById('lightPhi') as HTMLInputElement
  const paletteUi = document.getElementById('palette')!

  try {
    const gpu = await initGPU(canvas)
    const { device, format } = gpu

    // --- Build skeleton pipeline and bake once into the atlas texture. ---
    const loaded = await loadMixamoBake('/mixamo_running.json')
    const rig = loaded.rig
    const boneDisplay = chibiBoneDisplayMats(rig)
    const material = chibiMaterial(rig)
    const scales = rig.map(() => [1, 1, 1] as [number, number, number])
    const vat = bakeSkeletonVAT(device, rig, VAT_FRAMES, scales, loaded.sampler)

    // Atlas: RGBA8 storage for G-buffer output.
    const atlasTex = device.createTexture({
      label: 'atlas-gbuffer',
      size: { width: ATLAS_W, height: ATLAS_H },
      format: 'rgba8unorm',
      usage:
        GPUTextureUsage.RENDER_ATTACHMENT |
        GPUTextureUsage.TEXTURE_BINDING |
        GPUTextureUsage.COPY_DST,
    })
    const atlasView = atlasTex.createView()
    const atlasDepth = device.createTexture({
      label: 'atlas-depth',
      size: { width: ATLAS_W, height: ATLAS_H },
      format: 'depth24plus-stencil8',
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
    })
    const atlasDepthView = atlasDepth.createView()

    // Skeleton renderer targets the atlas format.
    const skeletonRenderer = createSkeletonRenderer(device, 'rgba8unorm', vat, boneDisplay, material)
    const viewMats = buildViewMatrices()

    // --- Bake pass: render every (view, frame) into its cell. ---
    statsEl.textContent = 'Baking atlas...'
    await new Promise((r) => requestAnimationFrame(r))

    const bakeStart = performance.now()

    // First: clear the entire atlas in one dedicated pass. All subsequent
    // bake passes use 'load' so previously-written cells stay intact.
    {
      const clearEnc = device.createCommandEncoder()
      const clearPass = clearEnc.beginRenderPass({
        colorAttachments: [
          {
            view: atlasView,
            loadOp: 'clear',
            storeOp: 'store',
            clearValue: { r: 0, g: 0.5, b: 0.5, a: 0 },
          },
        ],
      })
      clearPass.end()
      device.queue.submit([clearEnc.finish()])
    }

    const BATCH_FRAMES = 6
    for (let fStart = 0; fStart < VAT_FRAMES; fStart += BATCH_FRAMES) {
      const encoder = device.createCommandEncoder()
      for (let f = fStart; f < Math.min(fStart + BATCH_FRAMES, VAT_FRAMES); f++) {
        for (let v = 0; v < NUM_VIEWS; v++) {
          const pass = encoder.beginRenderPass({
            colorAttachments: [
              {
                view: atlasView,
                loadOp: 'load',                 // preserve all previously-drawn cells
                storeOp: 'store',
              },
            ],
            depthStencilAttachment: {
              view: atlasDepthView,
              depthLoadOp: 'clear',             // depth is scoped to the single cell; clear ok
              depthStoreOp: 'store',
              depthClearValue: 1.0,
              stencilLoadOp: 'clear',
              stencilStoreOp: 'store',
              stencilClearValue: 0,
            },
          })
          pass.setViewport(v * CELL_SIZE, f * CELL_SIZE, CELL_SIZE, CELL_SIZE, 0, 1)
          pass.setScissorRect(v * CELL_SIZE, f * CELL_SIZE, CELL_SIZE, CELL_SIZE)
          skeletonRenderer.draw(pass, viewMats[v].view, viewMats[v].proj, f, 1.0, 'gbuffer')
          pass.end()
        }
      }
      device.queue.submit([encoder.finish()])
      await device.queue.onSubmittedWorkDone()
    }
    const bakeMs = performance.now() - bakeStart

    // --- Consumer pipeline: sample atlas, decode, light, output. ---
    const consumerShader = device.createShaderModule({ code: CONSUMER_SHADER, label: 'consumer-shader' })
    const consumerPipeline = device.createRenderPipeline({
      label: 'consumer-pipeline',
      layout: 'auto',
      vertex: { module: consumerShader, entryPoint: 'vs_main' },
      fragment: {
        module: consumerShader,
        entryPoint: 'fs_main',
        targets: [{ format }],
      },
      primitive: { topology: 'triangle-list' },
    })
    const consumerSampler = device.createSampler({ magFilter: 'nearest', minFilter: 'nearest' })

    // Consumer uniform: uv0, uvSize, lightDir.  8 × f32 = 32 bytes.
    const consumerUniform = device.createBuffer({
      size: 32,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    })
    const consumerUniformData = new Float32Array(8)

    // Live-editable palette — initialized from material.palette, writable at runtime.
    const paletteBuffer = device.createBuffer({
      label: 'runtime-palette',
      size: material.palette.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    })
    device.queue.writeBuffer(paletteBuffer, 0, material.palette)

    const consumerBindGroup = device.createBindGroup({
      layout: consumerPipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: consumerUniform } },
        { binding: 1, resource: atlasView },
        { binding: 2, resource: consumerSampler },
        { binding: 3, resource: { buffer: paletteBuffer } },
      ],
    })

    // --- UI wiring ---
    let currentView = 4  // S — facing camera looks natural for chibi
    document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach((btn) => {
      btn.onclick = () => { currentView = Number(btn.dataset.view) }
    })

    // Palette color swatches
    const slotNames = Object.entries(material.namedSlots)
    const swatchEls: HTMLDivElement[] = []
    const currentColors = new Float32Array(material.palette)
    slotNames.forEach(([name, slot]) => {
      if (name === 'bg') return
      const wrap = document.createElement('div')
      wrap.style.display = 'flex'
      wrap.style.flexDirection = 'column'
      wrap.style.alignItems = 'center'
      wrap.style.gap = '2px'

      const swatch = document.createElement('div')
      swatch.className = 'swatch'
      const r = currentColors[slot * 4 + 0]
      const g = currentColors[slot * 4 + 1]
      const b = currentColors[slot * 4 + 2]
      swatch.style.backgroundColor = `rgb(${r * 255},${g * 255},${b * 255})`

      const input = document.createElement('input')
      input.type = 'color'
      input.value = '#' + [r, g, b].map((c) => Math.round(c * 255).toString(16).padStart(2, '0')).join('')
      input.style.width = '28px'
      input.style.height = '16px'
      input.oninput = () => {
        const hex = input.value.slice(1)
        const nr = parseInt(hex.slice(0, 2), 16) / 255
        const ng = parseInt(hex.slice(2, 4), 16) / 255
        const nb = parseInt(hex.slice(4, 6), 16) / 255
        currentColors[slot * 4 + 0] = nr
        currentColors[slot * 4 + 1] = ng
        currentColors[slot * 4 + 2] = nb
        device.queue.writeBuffer(paletteBuffer, slot * 16, new Float32Array([nr, ng, nb, 1]))
        swatch.style.backgroundColor = `rgb(${nr * 255},${ng * 255},${nb * 255})`
      }

      const label = document.createElement('span')
      label.textContent = name
      label.style.fontSize = '10px'

      wrap.appendChild(swatch)
      wrap.appendChild(input)
      wrap.appendChild(label)
      paletteUi.appendChild(wrap)
      swatchEls.push(swatch)
    })

    // --- Main render loop: sample cell (currentView, elapsed→frame). ---
    const loop = new FrameLoop()
    let elapsed = 0
    loop.onUpdate = (stats) => { elapsed += stats.dt }
    loop.onRender = (stats) => {
      const frameIdx = Math.floor((elapsed / loaded.durationSec) * VAT_FRAMES) % VAT_FRAMES

      // Compute atlas uv rect for this (view, frame).
      const u0 = (currentView * CELL_SIZE) / ATLAS_W
      const v0 = (frameIdx * CELL_SIZE) / ATLAS_H
      const du = CELL_SIZE / ATLAS_W
      const dv = CELL_SIZE / ATLAS_H

      // Light dir from sliders.
      const thetaDeg = Number(lightThetaEl.value)
      const phiDeg = Number(lightPhiEl.value)
      const theta = thetaDeg * Math.PI / 180
      const phi = phiDeg * Math.PI / 180
      const lx = Math.cos(phi) * Math.cos(theta)
      const ly = Math.sin(phi)
      const lz = Math.cos(phi) * Math.sin(theta)

      consumerUniformData[0] = u0
      consumerUniformData[1] = v0
      consumerUniformData[2] = du
      consumerUniformData[3] = dv
      consumerUniformData[4] = lx
      consumerUniformData[5] = ly
      consumerUniformData[6] = lz
      device.queue.writeBuffer(consumerUniform, 0, consumerUniformData)

      const encoder = device.createCommandEncoder()
      const canvasView = gpu.context.getCurrentTexture().createView()
      const pass = encoder.beginRenderPass({
        colorAttachments: [
          {
            view: canvasView,
            loadOp: 'clear',
            storeOp: 'store',
            clearValue: { r: 0.05, g: 0.05, b: 0.08, a: 1.0 },
          },
        ],
      })
      pass.setPipeline(consumerPipeline)
      pass.setBindGroup(0, consumerBindGroup)
      pass.draw(3)
      pass.end()
      device.queue.submit([encoder.finish()])

      statsEl.textContent = [
        `Bake time: ${bakeMs.toFixed(0)} ms`,
        `Atlas: ${ATLAS_W}×${ATLAS_H} (${(ATLAS_W * ATLAS_H * 4 / 1024 / 1024).toFixed(1)} MB GPU)`,
        `Views: ${NUM_VIEWS}   Frames: ${VAT_FRAMES}`,
        `Facing: ${VIEW_LABELS[currentView]}`,
        `Frame: ${frameIdx}`,
        `FPS: ${stats.fps.toFixed(0)}`,
        ``,
        `Runtime: atlas + palette + lightdir only.`,
        `The rig and VAT are not bound at display.`,
      ].join('\n')
    }
    loop.start()
  } catch (err) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU Error: ${err instanceof Error ? err.message : String(err)}`
    console.error(err)
  }
}

main()
