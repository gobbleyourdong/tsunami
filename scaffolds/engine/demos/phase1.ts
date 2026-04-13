/**
 * Phase 1 Demo: Spinning textured cube with camera controls.
 * Exercises: GPU init, shader compilation, vertex/index buffers,
 * render pipeline, depth buffer, uniform buffers, camera, frame loop.
 */

import {
  initGPU,
  resizeGPU,
  compileShader,
  createRenderPipeline,
  createVertexBuffer,
  createIndexBuffer,
  createUniformBuffer,
  updateBuffer,
  VERTEX_POSITION_NORMAL_UV,
  MESH_SHADER,
  Camera,
  FrameLoop,
  colorPass,
  createCubeGeometry,
  createPlaneGeometry,
} from '../src'
import { mat4 } from '../src/math/vec'

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const errorEl = document.getElementById('error')!

  try {
    const gpu = await initGPU(canvas)
    const { device, format } = gpu

    // Camera
    const camera = new Camera({
      position: [3, 4, 6],
      target: [0, 0.5, 0],
      controls: 'orbit',
      fov: 50,
    })
    const cleanup = camera.bindToCanvas(canvas)

    // Shader
    const shader = compileShader(device, MESH_SHADER, 'mesh-shader')

    // Pipeline
    const pipeline = createRenderPipeline(device, {
      label: 'mesh-pipeline',
      shader,
      vertexBuffers: [VERTEX_POSITION_NORMAL_UV],
      format,
      depthStencil: true,
      cullMode: 'back',
    })

    // Geometry
    const cube = createCubeGeometry(1.5)
    const cubeVB = createVertexBuffer(device, cube.vertices, 'cube-vb')
    const cubeIB = createIndexBuffer(device, cube.indices, 'cube-ib')

    const plane = createPlaneGeometry(12, 1)
    const planeVB = createVertexBuffer(device, plane.vertices, 'plane-vb')
    const planeIB = createIndexBuffer(device, plane.indices, 'plane-ib')

    // Uniform buffer: mvp + model + normalMatrix = 3 × mat4x4f = 192 bytes
    const uniformSize = 3 * 64
    const cubeUniforms = createUniformBuffer(device, uniformSize, 'cube-uniforms')
    const planeUniforms = createUniformBuffer(device, uniformSize, 'plane-uniforms')

    const cubeBindGroup = device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [{ binding: 0, resource: { buffer: cubeUniforms } }],
    })

    const planeBindGroup = device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [{ binding: 0, resource: { buffer: planeUniforms } }],
    })

    // Plane model matrix (static)
    const planeModel = mat4.create()
    mat4.translate(planeModel, planeModel, [0, -0.5, 0])

    const uniformData = new Float32Array(48) // 3 mat4

    // Frame loop
    const loop = new FrameLoop()

    let angle = 0

    loop.onUpdate = (stats) => {
      angle += stats.dt * 0.8
      resizeGPU(gpu)
      camera.setAspect(canvas.width, canvas.height)
      camera.update()
    }

    loop.onRender = (stats) => {
      const view = gpu.context.getCurrentTexture().createView()
      const encoder = device.createCommandEncoder()

      const pass = encoder.beginRenderPass(colorPass(view, gpu.depthView))
      pass.setPipeline(pipeline)

      // --- Draw cube ---
      const cubeModel = mat4.create()
      mat4.translate(cubeModel, cubeModel, [0, 1.0, 0])
      mat4.rotateY(cubeModel, cubeModel, angle)

      const cubeMVP = mat4.create()
      mat4.multiply(cubeMVP, camera.viewProjection, cubeModel)

      const cubeNormal = mat4.create()
      mat4.invert(cubeNormal, cubeModel)
      mat4.transpose(cubeNormal, cubeNormal)

      uniformData.set(cubeMVP, 0)
      uniformData.set(cubeModel, 16)
      uniformData.set(cubeNormal, 32)
      updateBuffer(device, cubeUniforms, uniformData)

      pass.setBindGroup(0, cubeBindGroup)
      pass.setVertexBuffer(0, cubeVB)
      pass.setIndexBuffer(cubeIB, 'uint32')
      pass.drawIndexed(cube.indexCount)

      // --- Draw plane ---
      const planeMVP = mat4.create()
      mat4.multiply(planeMVP, camera.viewProjection, planeModel)

      const planeNormal = mat4.create()
      mat4.invert(planeNormal, planeModel)
      mat4.transpose(planeNormal, planeNormal)

      uniformData.set(planeMVP, 0)
      uniformData.set(planeModel, 16)
      uniformData.set(planeNormal, 32)
      updateBuffer(device, planeUniforms, uniformData)

      pass.setBindGroup(0, planeBindGroup)
      pass.setVertexBuffer(0, planeVB)
      pass.setIndexBuffer(planeIB, 'uint32')
      pass.drawIndexed(plane.indexCount)

      pass.end()
      device.queue.submit([encoder.finish()])

      // Stats overlay
      const lines = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Frame: ${stats.frameTime.toFixed(1)}ms`,
        `Render: ${stats.renderTime.toFixed(1)}ms`,
        `Draw calls: 2`,
        `Orbit: drag to rotate, scroll to zoom`,
      ]
      statsEl.textContent = lines.join('\n')
    }

    loop.start()

    // Cleanup on unload
    window.addEventListener('beforeunload', () => {
      cleanup()
      loop.stop()
    })
  } catch (err) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU Error: ${err instanceof Error ? err.message : String(err)}`
    console.error(err)
  }
}

main()
