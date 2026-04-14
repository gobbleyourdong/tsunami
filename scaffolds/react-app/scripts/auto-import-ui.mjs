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

// Collect every identifier that's "in scope" at module level: imported names,
// function declarations, variable declarations, class declarations. Any of
// these shadows the UI component, so we must NOT inject an import for them.
function collectScopeBindings(ast) {
  const bindings = new Set()
  for (const node of ast.program.body) {
    if (node.type === "ImportDeclaration") {
      for (const spec of node.specifiers) {
        if (spec.local && spec.local.name) bindings.add(spec.local.name)
      }
    } else if (node.type === "FunctionDeclaration" && node.id) {
      bindings.add(node.id.name)
    } else if (node.type === "ClassDeclaration" && node.id) {
      bindings.add(node.id.name)
    } else if (node.type === "VariableDeclaration") {
      for (const decl of node.declarations) {
        if (decl.id && decl.id.type === "Identifier") bindings.add(decl.id.name)
      }
    } else if (node.type === "ExportNamedDeclaration" && node.declaration) {
      const decl = node.declaration
      if (decl.type === "FunctionDeclaration" && decl.id) bindings.add(decl.id.name)
      else if (decl.type === "ClassDeclaration" && decl.id) bindings.add(decl.id.name)
      else if (decl.type === "VariableDeclaration") {
        for (const d of decl.declarations) {
          if (d.id && d.id.type === "Identifier") bindings.add(d.id.name)
        }
      }
    } else if (node.type === "ExportDefaultDeclaration") {
      const decl = node.declaration
      if ((decl.type === "FunctionDeclaration" || decl.type === "ClassDeclaration") && decl.id) {
        bindings.add(decl.id.name)
      }
    }
  }
  return bindings
}

// Collect every PascalCase JSX opening element name. JSXMemberExpression
// (e.g. Card.Header) is flattened to its root ("Card").
function collectUsedPascalTags(ast) {
  const used = new Set()
  traverse(ast, {
    JSXOpeningElement(path) {
      let name = path.node.name
      while (name.type === "JSXMemberExpression") name = name.object
      if (name.type === "JSXIdentifier") {
        const n = name.name
        if (n[0] >= "A" && n[0] <= "Z") used.add(n)
      }
    },
  })
  return used
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

// Process one .tsx file. Returns { changed, added } where added is the list
// of names we injected.
function processFile(filePath, uiExports) {
  const source = readFileSync(filePath, "utf8")
  let ast
  try {
    ast = parseTS(source)
  } catch (e) {
    // Don't block the build on a parse error here — tsc/vite will report it
    // with better location info. Skip.
    return { changed: false, added: [] }
  }
  const scope = collectScopeBindings(ast)
  const used = collectUsedPascalTags(ast)

  // Missing = used, is a UI export, and not already in scope.
  const missing = []
  for (const tag of used) {
    if (uiExports.has(tag) && !scope.has(tag)) missing.push(tag)
  }
  if (missing.length === 0) return { changed: false, added: [] }

  const uiImport = findUIImport(ast)
  if (uiImport) {
    // Extend existing import: add specifiers for each missing name.
    for (const name of missing) {
      if (!hasSpecifier(uiImport, name)) {
        uiImport.specifiers.push(t.importSpecifier(t.identifier(name), t.identifier(name)))
      }
    }
  } else {
    // Prepend a new import at the top of the file.
    const newImport = t.importDeclaration(
      missing.map((n) => t.importSpecifier(t.identifier(n), t.identifier(n))),
      t.stringLiteral("./components/ui"),
    )
    ast.program.body.unshift(newImport)
  }

  const out = generate(ast, { retainLines: false, jsescOption: { minimal: true } }, source)
  writeFileSync(filePath, out.code)
  return { changed: true, added: missing }
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
    if (r.changed) report.push({ file: f.replace(PROJECT + "/", ""), added: r.added })
  }
  if (report.length > 0) {
    console.log("[auto-import-ui] injected UI imports:")
    for (const r of report) {
      console.log(`  ${r.file}: ${r.added.join(", ")}`)
    }
  }
}

main()
