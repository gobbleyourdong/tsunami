import { useState } from "react"
import { search, type SearchHit } from "../lib/search"

type Props = { onSelect: (slug: string) => void }

export default function SearchBox({ onSelect }: Props) {
  const [q, setQ] = useState("")
  const hits: SearchHit[] = q ? search(q, 6) : []
  return (
    <div className="searchbox">
      <input
        type="search"
        placeholder="Search docs…"
        value={q}
        onChange={e => setQ(e.target.value)}
      />
      {hits.length > 0 && (
        <ul className="results">
          {hits.map(h => (
            <li key={h.slug} onClick={() => { onSelect(h.slug); setQ("") }}>
              <strong>{h.title}</strong>
              <div style={{ fontSize: "0.78rem", opacity: 0.7 }}>{h.snippet}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
