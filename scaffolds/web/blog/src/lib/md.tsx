import type { ReactElement } from "react"

/**
 * Shared minimal markdown → React renderer. Same source as the
 * docs-site scaffold — keep the two in sync, or extract to a shared
 * scaffolds/engine helper once a third scaffold needs it.
 *
 * Supports headings (#/##/###), paragraphs, fenced code blocks, and
 * inline `code`. Output is plain React elements — no HTML injection
 * surface. Upgrade to react-markdown + remark-gfm when you need
 * lists, tables, links, bold/italic.
 */
export function renderMarkdown(src: string): ReactElement {
  const blocks: ReactElement[] = []
  const lines = src.split("\n")
  let i = 0
  let blockIndex = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.startsWith("```")) {
      const buf: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i])
        i++
      }
      i++
      blocks.push(
        <pre key={blockIndex++}>
          <code>{buf.join("\n")}</code>
        </pre>,
      )
      continue
    }

    if (line.startsWith("### ")) {
      blocks.push(<h3 key={blockIndex++}>{renderInline(line.slice(4))}</h3>)
      i++
      continue
    }
    if (line.startsWith("## ")) {
      blocks.push(<h2 key={blockIndex++}>{renderInline(line.slice(3))}</h2>)
      i++
      continue
    }
    if (line.startsWith("# ")) {
      blocks.push(<h1 key={blockIndex++}>{renderInline(line.slice(2))}</h1>)
      i++
      continue
    }

    if (line.trim() === "") {
      i++
      continue
    }

    const buf: string[] = [line]
    i++
    while (i < lines.length && lines[i].trim() !== "" && !lines[i].startsWith("#") && !lines[i].startsWith("```")) {
      buf.push(lines[i])
      i++
    }
    blocks.push(<p key={blockIndex++}>{renderInline(buf.join(" "))}</p>)
  }

  return <>{blocks}</>
}

function renderInline(text: string): (string | ReactElement)[] {
  const out: (string | ReactElement)[] = []
  const pattern = /`([^`]+)`/g
  const matches = [...text.matchAll(pattern)]
  let last = 0
  let keyIdx = 0
  for (const m of matches) {
    const start = m.index ?? 0
    if (start > last) out.push(text.slice(last, start))
    out.push(<code key={keyIdx++}>{m[1]}</code>)
    last = start + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}
