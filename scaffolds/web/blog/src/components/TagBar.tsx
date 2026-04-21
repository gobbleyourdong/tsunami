import { allTags } from "../data/posts"

type Props = { active: string; onSelect: (tag: string) => void }

export default function TagBar({ active, onSelect }: Props) {
  const tags = allTags()
  return (
    <div className="tags">
      <button className={active === "" ? "active" : ""} onClick={() => onSelect("")}>
        all
      </button>
      {tags.map(t => (
        <button
          key={t}
          className={active === t ? "active" : ""}
          onClick={() => onSelect(t)}
        >
          {t}
        </button>
      ))}
    </div>
  )
}
