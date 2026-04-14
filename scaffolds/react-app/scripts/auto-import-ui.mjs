// Pre-build transform: walk every src/**/*.tsx, find PascalCase JSX tags that
// aren't in scope (not imported, not locally declared) but ARE exported from
// ./components/ui, and inject them into the import. Kills the recurring
// model-drift where Gemma-4 writes <Alert> / <Progress> / <Badge> without
// adding them to the import line.
//
// Uses @babel/parser + @babel/traverse + @babel/generator AST — no regex.

import { readFileSync, writeFileSync, readdirSync, statSync } from "node:fs"
import { join, dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { parse } from "@babel/parser"
import _traverse from "@babel/traverse"
import _generate from "@babel/generator"
import * as t from "@babel/types"

const traverse = _traverse.default || _traverse
const generate = _generate.default || _generate

const __dirname = dirname(fileURLToPath(import.meta.url))
const PROJECT = resolve(__dirname, "..")
const UI_INDEX = join(PROJECT, "src/components/ui/index.ts")
const SRC_DIR = join(PROJECT, "src")

const UI_IMPORT_PATHS = new Set([
  "./components/ui",
  "./components/ui/index",
  "@/components/ui",
])

function parseTS(source) {
  return parse(source, {
    sourceType: "module",
    plugins: ["typescript", "jsx"],
  })
}

// Extract all exported names from components/ui/index.ts by walking
// ExportNamedDeclaration nodes. Handles both `export { X } from "./X"` and
// `export { default as X, Y, Z } from "./X"`.
function loadUIExports() {
  const source = readFileSync(UI_INDEX, "utf8")
  const ast = parseTS(source)
  const exports = new Set()
  traverse(ast, {
    ExportNamedDeclaration(path) {
      for (const spec of path.node.specifiers || []) {
        if (spec.type === "ExportSpecifier") {
          const name = spec.exported.name || spec.exported.value
          if (name) exports.add(name)
        }
      }
    },
  })
  return exports
}

function walkSrcTsx(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      if (entry === "node_modules" || entry === "dist") continue
      walkSrcTsx(full, out)
    } else if (entry.endsWith(".tsx") || entry.endsWith(".jsx")) {
      out.push(full)
    }
  }
  return out
}

// Walk the AST and for every PascalCase JSX tag, check if babel's scope
// analysis resolves the name in the scope where the tag appears. If it does
// (any enclosing function's const, a module import, a parameter, etc.), we
// leave it alone. If it doesn't, it's an "unresolved" tag we may need to
// either import from ./components/ui or fall back to as a passthrough.
//
// Returns two sets:
//   `simple`     — unresolved tag used as a plain <Name> at least once
//                  (safe to passthrough — a div fallback works)
//   `memberRoot` — unresolved tag used as <Name.Sub> (div passthrough would
//                  NOT work because the sub-property wouldn't exist; must
//                  come from a real import or be left alone for tsc)
function collectUnresolvedPascalTags(ast) {
  const simple = new Set()
  const memberRoot = new Set()
  traverse(ast, {
    JSXOpeningElement(path) {
      let name = path.node.name
      const isMember = name.type === "JSXMemberExpression"
      while (name.type === "JSXMemberExpression") name = name.object
      if (name.type !== "JSXIdentifier") return
      const n = name.name
      if (n[0] < "A" || n[0] > "Z") return
      // Babel's scope tracks bindings at every level: module, function, block.
      // If hasBinding(n) returns true, the name resolves somewhere up the
      // scope chain and we should leave it alone.
      if (path.scope.hasBinding(n)) return
      if (isMember) memberRoot.add(n)
      else simple.add(n)
    },
  })
  return { simple, memberRoot }
}

// Find the import declaration from one of the UI paths, if any, and return
// its node. Returns null if not present.
function findUIImport(ast) {
  for (const node of ast.program.body) {
    if (node.type === "ImportDeclaration" && UI_IMPORT_PATHS.has(node.source.value)) {
      return node
    }
  }
  return null
}

function hasSpecifier(importNode, name) {
  return importNode.specifiers.some(
    (s) => s.type === "ImportSpecifier" && (s.imported.name || s.imported.value) === name,
  )
}

// Build a passthrough component declaration: `const Name = (props: any) => <div {...props} />`
// TypeScript-friendly, renders children + forwards any props so layout roughly
// works. Used for PascalCase tags the model invented that don't exist anywhere.
function passthroughDecl(name) {
  const propsParam = t.identifier("props")
  propsParam.typeAnnotation = t.tsTypeAnnotation(t.tsAnyKeyword())
  const div = t.jsxElement(
    t.jsxOpeningElement(
      t.jsxIdentifier("div"),
      [t.jsxSpreadAttribute(t.identifier("props"))],
      false,
    ),
    t.jsxClosingElement(t.jsxIdentifier("div")),
    [],
    false,
  )
  const arrow = t.arrowFunctionExpression([propsParam], div)
  return t.variableDeclaration("const", [
    t.variableDeclarator(t.identifier(name), arrow),
  ])
}

// Process one .tsx file. Returns { changed, imported, passthrough } where
// `imported` are names we added to the ui import and `passthrough` are names
// we defined locally as <div {...props} /> fallbacks so the build doesn't fail.
function processFile(filePath, uiExports) {
  const source = readFileSync(filePath, "utf8")
  let ast
  try {
    ast = parseTS(source)
  } catch (e) {
    return { changed: false, imported: [], passthrough: [] }
  }
  const { simple, memberRoot } = collectUnresolvedPascalTags(ast)

  // Case 1: UI components — unresolved and named in uiExports. Inject imports.
  // Covers both <Name> and <Name.Sub> since the real component carries its
  // sub-properties.
  const toImport = []
  for (const tag of [...simple, ...memberRoot]) {
    if (uiExports.has(tag)) toImport.push(tag)
  }

  // Case 2: Model-invented components — unresolved and NOT in uiExports, used
  // as simple <Name> only. Inject a local passthrough so the app renders
  // instead of crashing. Tags appearing as <Name.Sub> are skipped because a
  // div fallback has no sub-properties — tsc will surface those.
  const toPassthrough = []
  for (const tag of simple) {
    if (!uiExports.has(tag) && !memberRoot.has(tag)) toPassthrough.push(tag)
  }

  if (toImport.length === 0 && toPassthrough.length === 0) {
    return { changed: false, imported: [], passthrough: [] }
  }

  if (toImport.length > 0) {
    const uiImport = findUIImport(ast)
    if (uiImport) {
      for (const name of toImport) {
        if (!hasSpecifier(uiImport, name)) {
          uiImport.specifiers.push(t.importSpecifier(t.identifier(name), t.identifier(name)))
        }
      }
    } else {
      const newImport = t.importDeclaration(
        toImport.map((n) => t.importSpecifier(t.identifier(n), t.identifier(n))),
        t.stringLiteral("./components/ui"),
      )
      ast.program.body.unshift(newImport)
    }
  }

  if (toPassthrough.length > 0) {
    for (const name of toPassthrough) ast.program.body.push(passthroughDecl(name))
  }

  const out = generate(ast, { retainLines: false, jsescOption: { minimal: true } }, source)
  writeFileSync(filePath, out.code)
  return { changed: true, imported: toImport, passthrough: toPassthrough }
}

function main() {
  let uiExports
  try {
    uiExports = loadUIExports()
  } catch (e) {
    console.error(`[auto-import-ui] could not read ${UI_INDEX}: ${e.message}`)
    process.exit(0) // don't block build
  }
  const files = walkSrcTsx(SRC_DIR)
  const report = []
  for (const f of files) {
    const r = processFile(f, uiExports)
    if (r.changed) {
      report.push({
        file: f.replace(PROJECT + "/", ""),
        imported: r.imported,
        passthrough: r.passthrough,
      })
    }
  }
  if (report.length > 0) {
    for (const r of report) {
      const parts = []
      if (r.imported.length) parts.push(`imported=${r.imported.join(",")}`)
      if (r.passthrough.length) parts.push(`passthrough=${r.passthrough.join(",")}`)
      console.log(`[auto-import-ui] ${r.file}: ${parts.join(" ")}`)
    }
  }
}

main()
