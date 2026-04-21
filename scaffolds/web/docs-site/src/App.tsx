import { useEffect, useState } from "react"
import { Sidebar, DocPage, SearchBox, ThemeToggle } from "./components"
import { listSlugs } from "./data/docs"

function initialSlug(): string {
  const hash = typeof window !== "undefined"
    ? window.location.hash.replace(/^#/, "")
    : ""
  const slugs = listSlugs()
  return slugs.includes(hash) ? hash : slugs[0] ?? "introduction"
}

export default function App() {
  const [slug, setSlug] = useState(initialSlug)

  useEffect(() => {
    if (typeof window !== "undefined") window.location.hash = slug
  }, [slug])

  return (
    <div className="layout">
      <Sidebar current={slug} onSelect={setSlug} />
      <div>
        <div style={{ padding: "1rem 3rem 0" }}>
          <SearchBox onSelect={setSlug} />
          <ThemeToggle />
        </div>
        <DocPage slug={slug} />
      </div>
    </div>
  )
}
