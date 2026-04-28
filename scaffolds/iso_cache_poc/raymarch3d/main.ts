// main.ts — bootstrap WebGPU, upload primitives + palette, render loop.

import { createRaymarchPipeline } from './pipeline.ts';
import {
  ASSETS,
  PRIM_STRIDE_FLOATS,
  packPalette,
  packPrimitives,
  type GPUPrim,
} from './assets.ts';

// ─────────── Status helper (writes to #status div) ───────────

function setStatus(msg: string, isError = false): void {
  const el = document.getElementById('status');
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle('err', isError);
}

// ─────────── Camera (fixed for Phase B; orbit added in Phase C) ───────────

interface Camera {
  pos: [number, number, number];
  dir: [number, number, number];
  right: [number, number, number];
  up: [number, number, number];
  orthoHalfW: number;
  orthoHalfH: number;
}

function defaultCamera(): Camera {
  return {
    pos: [0, 0, 1.5],
    dir: [0, 0, -1],
    right: [1, 0, 0],
    up: [0, 1, 0],
    orthoHalfW: 0.6,
    orthoHalfH: 0.6,
  };
}

// ─────────── Uniform layout (192 bytes; 48 floats) ───────────
//
//   slot 0..3   cameraPos.xyz, _pad
//   slot 4..7   cameraDir.xyz, _pad
//   slot 8..11  cameraRight.xyz, _pad
//   slot 12..15 cameraUp.xyz, _pad
//   slot 16..19 orthoHalfW, orthoHalfH, canvasW, canvasH
//   slot 20..23 numPrims (u32), maxSteps (u32), time, _pad

const UNIFORM_FLOATS = 48;
const UNIFORM_BYTES = UNIFORM_FLOATS * 4;
const MAX_STEPS = 64;

function writeUniforms(
  buf: Float32Array,
  cam: Camera,
  canvasW: number,
  canvasH: number,
  numPrims: number,
  time: number,
): void {
  buf[0]  = cam.pos[0];   buf[1]  = cam.pos[1];   buf[2]  = cam.pos[2];   buf[3]  = 0;
  buf[4]  = cam.dir[0];   buf[5]  = cam.dir[1];   buf[6]  = cam.dir[2];   buf[7]  = 0;
  buf[8]  = cam.right[0]; buf[9]  = cam.right[1]; buf[10] = cam.right[2]; buf[11] = 0;
  buf[12] = cam.up[0];    buf[13] = cam.up[1];    buf[14] = cam.up[2];    buf[15] = 0;
  buf[16] = cam.orthoHalfW;
  buf[17] = cam.orthoHalfH;
  buf[18] = canvasW;
  buf[19] = canvasH;
  // numPrims and maxSteps are u32 — write via DataView
  const u32 = new Uint32Array(buf.buffer, buf.byteOffset, UNIFORM_FLOATS);
  u32[20] = numPrims;
  u32[21] = MAX_STEPS;
  buf[22] = time;
  buf[23] = 0;
}

// ─────────── Bootstrap ───────────

interface Renderer {
  device: GPUDevice;
  context: GPUCanvasContext;
  format: GPUTextureFormat;
  pipeline: GPURenderPipeline;
  bindGroupLayout: GPUBindGroupLayout;
  uniformBuffer: GPUBuffer;
  uniformData: Float32Array;
  primsBuffer: GPUBuffer;
  primsCapacity: number;
  paletteBuffer: GPUBuffer;
  bindGroup: GPUBindGroup;
  numPrims: number;
  cam: Camera;
  canvas: HTMLCanvasElement;
}

async function bootstrap(canvas: HTMLCanvasElement): Promise<Renderer | null> {
  if (!navigator.gpu) {
    setStatus('WebGPU is not available in this browser.', true);
    return null;
  }
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) {
    setStatus('No WebGPU adapter available.', true);
    return null;
  }
  const device = await adapter.requestDevice();
  const context = canvas.getContext('webgpu') as GPUCanvasContext | null;
  if (!context) {
    setStatus('Failed to acquire WebGPU canvas context.', true);
    return null;
  }
  const format = navigator.gpu.getPreferredCanvasFormat();
  context.configure({ device, format, alphaMode: 'opaque' });

  const { pipeline, bindGroupLayout } = createRaymarchPipeline(device, format);

  const uniformBuffer = device.createBuffer({
    label: 'raymarch3d-uniforms',
    size: UNIFORM_BYTES,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const uniformData = new Float32Array(UNIFORM_FLOATS);

  // Initial primitives buffer is tiny; uploadPrimitives will grow it.
  const initialCap = 16;
  const primsBuffer = device.createBuffer({
    label: 'raymarch3d-primitives',
    size: initialCap * PRIM_STRIDE_FLOATS * 4,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  });

  const paletteData = packPalette();
  const paletteBuffer = device.createBuffer({
    label: 'raymarch3d-palette',
    size: paletteData.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  });
  device.queue.writeBuffer(paletteBuffer, 0, paletteData);

  const bindGroup = device.createBindGroup({
    label: 'raymarch3d-bg',
    layout: bindGroupLayout,
    entries: [
      { binding: 0, resource: { buffer: uniformBuffer } },
      { binding: 1, resource: { buffer: primsBuffer } },
      { binding: 2, resource: { buffer: paletteBuffer } },
    ],
  });

  return {
    device, context, format, pipeline, bindGroupLayout,
    uniformBuffer, uniformData,
    primsBuffer, primsCapacity: initialCap,
    paletteBuffer, bindGroup,
    numPrims: 0, cam: defaultCamera(), canvas,
  };
}

function uploadPrimitives(r: Renderer, prims: GPUPrim[]): void {
  const data = packPrimitives(prims);
  // Grow primsBuffer if needed (then rebuild the bind group)
  if (prims.length > r.primsCapacity) {
    r.primsBuffer.destroy();
    r.primsCapacity = Math.max(prims.length, r.primsCapacity * 2);
    r.primsBuffer = r.device.createBuffer({
      label: 'raymarch3d-primitives',
      size: r.primsCapacity * PRIM_STRIDE_FLOATS * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    r.bindGroup = r.device.createBindGroup({
      label: 'raymarch3d-bg',
      layout: r.bindGroupLayout,
      entries: [
        { binding: 0, resource: { buffer: r.uniformBuffer } },
        { binding: 1, resource: { buffer: r.primsBuffer } },
        { binding: 2, resource: { buffer: r.paletteBuffer } },
      ],
    });
  }
  r.device.queue.writeBuffer(r.primsBuffer, 0, data);
  r.numPrims = prims.length;
}

function renderFrame(r: Renderer, time: number): void {
  writeUniforms(r.uniformData, r.cam, r.canvas.width, r.canvas.height, r.numPrims, time);
  r.device.queue.writeBuffer(r.uniformBuffer, 0, r.uniformData);

  const view = r.context.getCurrentTexture().createView();
  const encoder = r.device.createCommandEncoder({ label: 'raymarch3d-encoder' });
  const pass = encoder.beginRenderPass({
    label: 'raymarch3d-pass',
    colorAttachments: [
      {
        view,
        clearValue: { r: 0.05, g: 0.06, b: 0.08, a: 1 },
        loadOp: 'clear',
        storeOp: 'store',
      },
    ],
  });
  pass.setPipeline(r.pipeline);
  pass.setBindGroup(0, r.bindGroup);
  pass.draw(3, 1, 0, 0);
  pass.end();
  r.device.queue.submit([encoder.finish()]);
}

// ─────────── Asset switcher UI ───────────

function buildAssetButtons(r: Renderer, container: HTMLElement, defaultName: string): void {
  for (const name of Object.keys(ASSETS)) {
    const btn = document.createElement('button');
    btn.textContent = name;
    if (name === defaultName) btn.classList.add('active');
    btn.addEventListener('click', () => {
      const prims = ASSETS[name]();
      uploadPrimitives(r, prims);
      // Highlight active
      for (const b of container.querySelectorAll('button')) b.classList.remove('active');
      btn.classList.add('active');
      setStatus(`Loaded asset "${name}" — ${prims.length} primitives.`);
    });
    container.appendChild(btn);
  }
}

// ─────────── Entry ───────────

async function main(): Promise<void> {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement | null;
  if (!canvas) { setStatus('No #canvas element on page.', true); return; }
  setStatus('Requesting WebGPU device…');
  const r = await bootstrap(canvas);
  if (!r) return;

  // Initial asset
  const firstAsset = Object.keys(ASSETS)[0];
  uploadPrimitives(r, ASSETS[firstAsset]());
  setStatus(`Rendering "${firstAsset}" — ${r.numPrims} primitives.`);

  // Asset switcher
  const buttons = document.getElementById('asset-buttons');
  if (buttons) buildAssetButtons(r, buttons, firstAsset);

  // Render loop (static camera for Phase B)
  let t0 = performance.now();
  const tick = (): void => {
    const t = (performance.now() - t0) / 1000;
    renderFrame(r, t);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

main().catch((err: unknown) => {
  setStatus('Bootstrap failed: ' + String(err), true);
  console.error(err);
});
