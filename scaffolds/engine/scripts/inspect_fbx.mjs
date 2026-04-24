/**
 * FBX structural inspection — parses Running.fbx and prints top-level
 * node types + counts. One-shot exploration to guide extraction code.
 */

import { parseBinary } from 'fbx-parser'
import { readFileSync } from 'node:fs'

const FBX_PATH = process.argv[2] ?? '/home/jb/Downloads/Running.fbx'
const buf = readFileSync(FBX_PATH)
const fbx = parseBinary(buf)

function printTree(nodes, depth = 0, maxDepth = 2) {
  if (depth > maxDepth) return
  for (const n of nodes) {
    const propSummary = n.props
      ? n.props.map((p) => (typeof p === 'string' ? JSON.stringify(p).slice(0, 40) : Array.isArray(p) ? `[${p.length}]` : typeof p)).join(',')
      : ''
    console.log(`${'  '.repeat(depth)}${n.name}  (${propSummary})`)
    if (n.nodes) printTree(n.nodes, depth + 1, maxDepth)
  }
}

console.log('=== TOP LEVEL ===')
printTree(fbx, 0, 0)

console.log('\n=== OBJECT TYPES (depth 2) ===')
const objects = fbx.find((n) => n.name === 'Objects')
if (objects && objects.nodes) {
  const counts = {}
  for (const obj of objects.nodes) {
    const subtype = obj.props[2]
    const key = `${obj.name}::${subtype}`
    counts[key] = (counts[key] ?? 0) + 1
  }
  Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .forEach(([k, v]) => console.log(`  ${v.toString().padStart(5)}  ${k}`))
}

console.log('\n=== GLOBAL SETTINGS (fps, time span) ===')
const gs = fbx.find((n) => n.name === 'GlobalSettings')
if (gs) {
  const props = gs.nodes.find((n) => n.name === 'Properties70')
  if (props) {
    for (const p of props.nodes) {
      if (p.name === 'P' && /FrameRate|Time|Unit/i.test(p.props[0] ?? '')) {
        console.log(`  ${p.props[0]}: ${p.props[4] ?? p.props[3] ?? '(no val)'}`)
      }
    }
  }
}

console.log('\n=== SAMPLE LimbNode ===')
const sampleBone = objects?.nodes.find((n) => n.name === 'Model' && n.props[2] === 'LimbNode')
if (sampleBone) {
  console.log('  name:', sampleBone.props[1])
  console.log('  id:', sampleBone.props[0])
  printTree(sampleBone.nodes, 1, 2)
}

console.log('\n=== SAMPLE AnimationCurve ===')
const sampleCurve = objects?.nodes.find((n) => n.name === 'AnimationCurve')
if (sampleCurve) {
  console.log('  id:', sampleCurve.props[0])
  for (const sub of sampleCurve.nodes ?? []) {
    const len = Array.isArray(sub.props?.[0]) ? sub.props[0].length : '-'
    console.log(`  ${sub.name}: ${typeof sub.props?.[0]} [${len}]`)
  }
}
