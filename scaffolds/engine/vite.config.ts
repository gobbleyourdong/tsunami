import { defineConfig } from 'vite'
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Modeler agent-loop middleware: POSTs from the in-page modeler write the
 * latest atlas + spec to disk under public/sdf_modeler/. The agent reads
 * those files directly and writes inbox.ark.json to push spec changes back.
 *
 * Endpoints:
 *   POST /__modeler/save_image  body: { name, dataUrl }  → public/sdf_modeler/<name>
 *   POST /__modeler/save_spec   body: { name, spec }     → public/sdf_modeler/<name>
 */
function modelerAgentLoop() {
  return {
    name: 'modeler-agent-loop',
    configureServer(server: { middlewares: { use: (path: string, fn: (req: any, res: any) => void) => void } }) {
      const out = resolve(__dirname, 'public/sdf_modeler')
      mkdirSync(out, { recursive: true })

      const readBody = (req: { on: (ev: string, cb: (chunk?: string) => void) => void }): Promise<string> => new Promise((res, rej) => {
        let buf = ''
        req.on('data', (c) => { buf += c })
        req.on('end', () => res(buf))
        req.on('error', rej)
      })

      server.middlewares.use('/__modeler/save_image', async (req, res) => {
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return }
        try {
          const { name, dataUrl } = JSON.parse(await readBody(req))
          if (!/^[a-zA-Z0-9._-]+$/.test(name)) throw new Error('bad name')
          const png = Buffer.from(String(dataUrl).split(',')[1], 'base64')
          writeFileSync(resolve(out, name), png)
          res.statusCode = 200; res.end('ok')
        } catch (e: unknown) {
          res.statusCode = 400; res.end(`err: ${(e as Error).message}`)
        }
      })

      server.middlewares.use('/__modeler/save_spec', async (req, res) => {
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return }
        try {
          const { name, spec } = JSON.parse(await readBody(req))
          if (!/^[a-zA-Z0-9._-]+$/.test(name)) throw new Error('bad name')
          writeFileSync(resolve(out, name), JSON.stringify(spec, null, 2))
          res.statusCode = 200; res.end('ok')
        } catch (e: unknown) {
          res.statusCode = 400; res.end(`err: ${(e as Error).message}`)
        }
      })
    },
  }
}

export default defineConfig({
  root: 'demos',
  publicDir: '../public',
  plugins: [modelerAgentLoop()],
  server: {
    port: 5173,
    open: false,
  },
  resolve: {
    alias: {
      '@engine': '/src',
    },
  },
  assetsInclude: ['**/*.wgsl'],
})
