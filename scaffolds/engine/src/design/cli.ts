// design/cli.ts — subprocess entrypoint for the Tsunami Python side.
//
// Reads a DesignScript JSON on stdin, validates + compiles it to a
// GameDefinition, writes the GameDefinition as JSON on stdout. Errors
// (invalid JSON, validation failures, compile exceptions) surface as
// structured JSON on stderr with a non-zero exit code.
//
// Invocation (from tsunami/tools/emit_design.py):
//   node --import tsx scaffolds/engine/src/design/cli.ts
//   < design.json > game_def.json  2> errors.json
//
// The stderr format is always a JSON object, never raw text, so the
// Python side can parse it uniformly.

import { validate } from './validate'
import { compile } from './compiler'
import type { DesignScript } from './schema'

async function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = ''
    process.stdin.setEncoding('utf8')
    process.stdin.on('data', chunk => { data += chunk })
    process.stdin.on('end', () => resolve(data))
    process.stdin.on('error', reject)
  })
}

function writeErr(payload: unknown): void {
  process.stderr.write(JSON.stringify(payload) + '\n')
}

async function main(): Promise<number> {
  let raw: string
  try {
    raw = await readStdin()
  } catch (e) {
    writeErr({ stage: 'read', message: `stdin read failed: ${(e as Error).message}` })
    return 2
  }

  let design: DesignScript
  try {
    design = JSON.parse(raw) as DesignScript
  } catch (e) {
    writeErr({ stage: 'parse', message: `input is not valid JSON: ${(e as Error).message}` })
    return 3
  }

  const result = validate(design)
  if (!result.ok) {
    writeErr({ stage: 'validate', errors: result.errors })
    return 4
  }

  let game
  try {
    game = compile(result.design)
  } catch (e) {
    writeErr({ stage: 'compile', message: `compiler threw: ${(e as Error).message}`,
               stack: (e as Error).stack })
    return 5
  }

  process.stdout.write(JSON.stringify(game, null, 2))
  return 0
}

main().then(code => process.exit(code)).catch(e => {
  writeErr({ stage: 'fatal', message: (e as Error).message, stack: (e as Error).stack })
  process.exit(1)
})
