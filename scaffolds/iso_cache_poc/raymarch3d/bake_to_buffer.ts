// bake_to_buffer.ts — one-shot WebGPU raymarch into an offscreen texture,
// readback to CPU as RGBA. Output is shape-compatible with the 2D demo's
// `colorBuf` ImageData → bridge primitive between the 3D-SDF renderer and
// the iso pixel cache.

import { createRaymarchPipeline } from './pipeline.ts';
import {
  PRIM_STRIDE_FLOATS,
  packPalette,
  packPrimitives,
  type GPUPrim,
} from './assets.ts';

const UNIFORM_FLOATS = 48;
const UNIFORM_BYTES = UNIFORM_FLOATS * 4;
const MAX_STEPS = 64;

interface CameraSpec {
  pos: [number, number, number];
  dir: [number, number, number];
  right: [number, number, number];
  up: [number, number, number];
  orthoHalfW: number;
  orthoHalfH: number;
}

const DEFAULT_CAM: CameraSpec = {
  pos: [0, 0, 1.5],
  dir: [0, 0, -1],
  right: [1, 0, 0],
  up: [0, 1, 0],
  orthoHalfW: 0.6,
  orthoHalfH: 0.6,
};

export interface BakeOptions {
  /** Square buffer size in pixels (one number; both dimensions equal). */
  size?: number;
  /** Override the default fixed camera. */
  camera?: CameraSpec;
}

/**
 * Bake a 3D-SDF asset (primitive list) to an RGBA pixel buffer via a
 * one-shot WebGPU render pass + texture readback. Returns null if WebGPU
 * is unavailable or any step fails (logged to console.warn).
 *
 * The returned buffer has length = size² × 4 bytes (RGBA8 unorm).
 */
export async function bakeAssetToImageData(
  prims: GPUPrim[],
  options: BakeOptions = {},
): Promise<Uint8ClampedArray | null> {
  const size = options.size ?? 96;
  const cam = options.camera ?? DEFAULT_CAM;

  if (!('gpu' in navigator) || !navigator.gpu) {
    console.warn('[bake_to_buffer] WebGPU not available');
    return null;
  }
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) {
    console.warn('[bake_to_buffer] No WebGPU adapter');
    return null;
  }
  const device = await adapter.requestDevice();

  const format: GPUTextureFormat = 'rgba8unorm';
  const { pipeline, bindGroupLayout } = createRaymarchPipeline(device, format);

  // Offscreen render target
  const texture = device.createTexture({
    label: 'bake-target',
    size: [size, size, 1],
    format,
    usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC,
  });
  const textureView = texture.createView();

  // Uniforms
  const uniformBuffer = device.createBuffer({
    label: 'bake-uniforms',
    size: UNIFORM_BYTES,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const uniformData = new Float32Array(UNIFORM_FLOATS);
  writeUniforms(uniformData, cam, size, size, prims.length);
  device.queue.writeBuffer(uniformBuffer, 0, uniformData);

  // Primitives
  const primsData = packPrimitives(prims);
  const primsBuffer = device.createBuffer({
    label: 'bake-primitives',
    size: Math.max(primsData.byteLength, PRIM_STRIDE_FLOATS * 4),
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  });
  device.queue.writeBuffer(primsBuffer, 0, primsData);

  // Palette
  const paletteData = packPalette();
  const paletteBuffer = device.createBuffer({
    label: 'bake-palette',
    size: paletteData.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  });
  device.queue.writeBuffer(paletteBuffer, 0, paletteData);

  const bindGroup = device.createBindGroup({
    label: 'bake-bg',
    layout: bindGroupLayout,
    entries: [
      { binding: 0, resource: { buffer: uniformBuffer } },
      { binding: 1, resource: { buffer: primsBuffer } },
      { binding: 2, resource: { buffer: paletteBuffer } },
    ],
  });

  // Encode the render + the texture→buffer copy. WebGPU requires
  // bytesPerRow to be a multiple of 256 for copyTextureToBuffer.
  const bytesPerRow = Math.ceil((size * 4) / 256) * 256;
  const readBuffer = device.createBuffer({
    label: 'bake-readback',
    size: bytesPerRow * size,
    usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
  });

  const encoder = device.createCommandEncoder({ label: 'bake-encoder' });
  const pass = encoder.beginRenderPass({
    label: 'bake-pass',
    colorAttachments: [
      {
        view: textureView,
        clearValue: { r: 0, g: 0, b: 0, a: 0 },
        loadOp: 'clear',
        storeOp: 'store',
      },
    ],
  });
  pass.setPipeline(pipeline);
  pass.setBindGroup(0, bindGroup);
  pass.draw(3, 1, 0, 0);
  pass.end();
  encoder.copyTextureToBuffer(
    { texture },
    { buffer: readBuffer, bytesPerRow, rowsPerImage: size },
    [size, size, 1],
  );
  device.queue.submit([encoder.finish()]);

  // Wait for the copy to finish, map, copy out without the row padding.
  await readBuffer.mapAsync(GPUMapMode.READ);
  const padded = new Uint8Array(readBuffer.getMappedRange());
  const tight = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    const srcRow = y * bytesPerRow;
    const dstRow = y * size * 4;
    for (let x = 0; x < size * 4; x++) {
      tight[dstRow + x] = padded[srcRow + x];
    }
  }
  readBuffer.unmap();

  // Cleanup transient resources
  readBuffer.destroy();
  texture.destroy();
  uniformBuffer.destroy();
  primsBuffer.destroy();
  paletteBuffer.destroy();

  return tight;
}

function writeUniforms(
  buf: Float32Array,
  cam: CameraSpec,
  canvasW: number,
  canvasH: number,
  numPrims: number,
): void {
  buf[0]  = cam.pos[0];   buf[1]  = cam.pos[1];   buf[2]  = cam.pos[2];   buf[3]  = 0;
  buf[4]  = cam.dir[0];   buf[5]  = cam.dir[1];   buf[6]  = cam.dir[2];   buf[7]  = 0;
  buf[8]  = cam.right[0]; buf[9]  = cam.right[1]; buf[10] = cam.right[2]; buf[11] = 0;
  buf[12] = cam.up[0];    buf[13] = cam.up[1];    buf[14] = cam.up[2];    buf[15] = 0;
  buf[16] = cam.orthoHalfW;
  buf[17] = cam.orthoHalfH;
  buf[18] = canvasW;
  buf[19] = canvasH;
  const u32 = new Uint32Array(buf.buffer, buf.byteOffset, UNIFORM_FLOATS);
  u32[20] = numPrims;
  u32[21] = MAX_STEPS;
  buf[22] = 0;
  buf[23] = 0;
}
