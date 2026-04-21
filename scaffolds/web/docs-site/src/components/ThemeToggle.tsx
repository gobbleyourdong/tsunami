import { useEffect, useState } from "react"

export default function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    typeof document !== "undefined" &&
    document.documentElement.getAttribute("data-theme") === "dark",
  )
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light")
  }, [dark])
  return (
    <button className="theme-toggle" onClick={() => setDark(d => !d)}>
      {dark ? "Light mode" : "Dark mode"}
    </button>
  )
}
