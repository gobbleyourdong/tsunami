import { useEffect, useState } from "react"
import { PostList, PostDetail, TagBar } from "./components"
import { findPost } from "./data/posts"

function initialSlug(): string {
  if (typeof window === "undefined") return ""
  const hash = window.location.hash.replace(/^#/, "")
  return hash && findPost(hash) ? hash : ""
}

export default function App() {
  const [slug, setSlug] = useState(initialSlug)
  const [tag, setTag] = useState("")

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.location.hash = slug
    }
  }, [slug])

  return (
    <div className="layout">
      <header className="header">
        <button className="h1" onClick={() => setSlug("")}>
          <h1>The Blog</h1>
        </button>
        {!slug && <TagBar active={tag} onSelect={setTag} />}
      </header>
      {slug
        ? <PostDetail slug={slug} onBack={() => setSlug("")} />
        : <PostList tag={tag} onSelect={setSlug} />}
    </div>
  )
}
