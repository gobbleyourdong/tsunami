#!/usr/bin/env node
/**
 * Prebuild hook — engine_handoff_001 §C.
 *
 * Ensures the `public/` tree exists and invokes the Python-side asset
 * bakers (`tools/font_bake.py`, `tools/build_sprites.py`) when inputs
 * are present. Runs automatically before `npm run dev` / `npm run build`
 * via the `prebuild` npm script.
 *
 * Non-fatal by design. Missing Python, missing font file, missing
 * assets manifest → warn and move on. Demos that don't need the baked
 * artifacts (no text, no sprites) still build cleanly.
 *
 * Environment variables:
 *   DEFAULT_FONT_TTF — path to a TTF/OTF file. When set, the script
 *     runs font_bake.py unless public/fonts/regular.atlas.bin exists.
 *   ASSETS_MANIFEST  — path to an assets.manifest.json (defaults to
 *     ./assets.manifest.json if the file exists). Absent → skip sprite
 *     build.
 *   PYTHON           — override the Python interpreter (default: python3).
 *
 * All paths below are resolved relative to the scaffold root
 * (scaffolds/engine/), not the repo root.
 */

import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCAFFOLD_ROOT = resolve(__dirname, '..')
const PUBLIC_DIR = resolve(SCAFFOLD_ROOT, 'public')
const FONTS_DIR = resolve(PUBLIC_DIR, 'fonts')
const SPRITES_DIR = resolve(PUBLIC_DIR, 'sprites')

const PYTHON = process.env.PYTHON || 'python3'

function log(label, msg) {
  // prefix each line so the output interleaves cleanly with vite's.
  process.stderr.write(`[prebuild] ${label}: ${msg}\n`)
}

function ensureDir(p) {
  if (!existsSync(p)) {
    mkdirSync(p, { recursive: true })
    log('mkdir', p.replace(SCAFFOLD_ROOT + '/', ''))
  }
}

function runPython(scriptRelative, args, reason) {
  const script = resolve(SCAFFOLD_ROOT, scriptRelative)
  if (!existsSync(script)) {
    log('skip', `${scriptRelative} not found (${reason})`)
    return false
  }
  const result = spawnSync(PYTHON, [script, ...args], {
    cwd: SCAFFOLD_ROOT,
    stdio: ['ignore', 'inherit', 'inherit'],
  })
  if (result.error) {
    if (result.error.code === 'ENOENT') {
      log('warn', `${PYTHON} not on PATH — skipping ${reason}. ` +
        `Install Python 3.9+ and the script's deps (fonttools numpy pillow) to enable.`)
      return false
    }
    log('warn', `spawn failed for ${reason}: ${result.error.message}`)
    return false
  }
  if (result.status !== 0) {
    log('warn', `${scriptRelative} exited ${result.status} — artifacts may be stale for ${reason}`)
    return false
  }
  return true
}

function maybeBakeFont() {
  const ttf = process.env.DEFAULT_FONT_TTF
  const target = resolve(FONTS_DIR, 'regular.atlas.bin')
  if (existsSync(target)) {
    log('font', `atlas present at ${target.replace(SCAFFOLD_ROOT + '/', '')} — skipping bake`)
    return
  }
  if (!ttf) {
    log('font',
      'DEFAULT_FONT_TTF not set; skipping font bake. ' +
      'Set DEFAULT_FONT_TTF=/path/to/font.ttf to enable the text demos.')
    return
  }
  if (!existsSync(ttf)) {
    log('warn', `DEFAULT_FONT_TTF=${ttf} does not exist — skipping font bake`)
    return
  }
  const outPrefix = resolve(FONTS_DIR, 'regular')
  runPython('tools/font_bake.py', [ttf, '--out', outPrefix], 'font bake')
}

function maybeBuildSprites() {
  const manifestPath = process.env.ASSETS_MANIFEST ||
    resolve(SCAFFOLD_ROOT, 'assets.manifest.json')
  if (!existsSync(manifestPath)) {
    log('sprites', 'no assets.manifest.json — skipping sprite build')
    return
  }
  try {
    if (!statSync(manifestPath).isFile()) {
      log('warn', `ASSETS_MANIFEST=${manifestPath} exists but is not a file — skipping`)
      return
    }
  } catch {
    return
  }
  runPython('tools/build_sprites.py',
    ['--project', SCAFFOLD_ROOT,
      '--manifest', manifestPath],
    'sprite build')
}

function main() {
  ensureDir(PUBLIC_DIR)
  ensureDir(FONTS_DIR)
  ensureDir(SPRITES_DIR)
  maybeBakeFont()
  maybeBuildSprites()
  log('ok', 'prebuild complete')
}

main()
