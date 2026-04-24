import { readFileSync } from 'node:fs'
import { parseBinary } from 'fbx-parser'

const IN = process.argv[2] ?? '/home/jb/Downloads/Running.fbx'
const fbx = parseBinary(readFileSync(IN))

function summary(node, depth = 0, max = 3) {
  if (depth > max) return
  const pad = '  '.repeat(depth)
  const name = node.name
  const propsShort = (node.props ?? []).slice(0, 3).map((p) => {
    if (typeof p === 'string') return `"${p.slice(0, 40)}"`
    if (Array.isArray(p)) return `[${p.length} elts]`
    return String(p).slice(0, 20)
  }).join(', ')
  console.log(`${pad}${name}(${propsShort})  [${node.nodes?.length ?? 0} child]`)
  for (const c of node.nodes ?? []) summary(c, depth + 1, max)
}

console.log('Top-level:')
for (const n of fbx) console.log(` ${n.name}  props=${(n.props ?? []).length}  children=${(n.nodes ?? []).length}`)
console.log()

// Find Objects section for Model / AnimationCurve counts
const objects = fbx.find((n) => n.name === 'Objects')
if (objects) {
  const tally = {}
  for (const c of objects.nodes) tally[c.name] = (tally[c.name] ?? 0) + 1
  console.log('Objects counts:', tally)
  // Sample one Model to see TRS data
  const aModel = objects.nodes.find((c) => c.name === 'Model')
  if (aModel) {
    console.log('\nSample Model:')
    summary(aModel, 0, 3)
  }
  // Sample one AnimationCurve
  const aCurve = objects.nodes.find((c) => c.name === 'AnimationCurve')
  if (aCurve) {
    console.log('\nSample AnimationCurve:')
    summary(aCurve, 0, 2)
  }
  const aCurveNode = objects.nodes.find((c) => c.name === 'AnimationCurveNode')
  if (aCurveNode) {
    console.log('\nSample AnimationCurveNode:')
    summary(aCurveNode, 0, 2)
  }
}

// Take count
const conns = fbx.find((n) => n.name === 'Connections')
if (conns) console.log(`\nConnections: ${conns.nodes.length}`)
