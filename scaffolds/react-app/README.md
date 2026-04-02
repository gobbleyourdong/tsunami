# React App Template

React 19 + TypeScript + Vite. Dark theme pre-configured.

## Build Loop

1. Write `src/App.tsx` FIRST — import your planned components (files don't exist yet, that's fine)
2. Start with `import "./index.css"` in App.tsx
3. Write types in `src/types.ts`
4. Write components in `src/components/` — one per file, under 100 lines
5. Run `npx vite build` to compile-check. Fix any errors.

## File Structure

```
src/
  App.tsx          ← Main app (write this FIRST)
  main.tsx         ← Entry point (don't edit)
  index.css        ← Dark theme + utilities (don't edit)
  types.ts         ← Your interfaces
  components/      ← One component per file
```

## CSS Utilities (use via className)

Layout: `.container` `.card` `.flex` `.grid` `.grid-2` `.grid-3` `.grid-4`
Spacing: `.gap-2` `.gap-4` `.gap-6` `.mt-4` `.mb-4` `.p-4`
Text: `.text-center` `.text-muted`

All `<button>`, `<input>`, `<table>`, `<a>` are auto-styled. No custom CSS needed.

## Component Patterns

### App with sidebar + content
```tsx
export default function App() {
  return (
    <div className="flex" style={{ height: "100vh" }}>
      <nav style={{ width: 220, borderRight: "1px solid var(--border)", padding: 16 }}>
        <h2>Menu</h2>
        <button onClick={() => setPage("home")}>Home</button>
        <button onClick={() => setPage("settings")}>Settings</button>
      </nav>
      <main className="container" style={{ flex: 1, overflow: "auto" }}>
        {page === "home" && <Home />}
        {page === "settings" && <Settings />}
      </main>
    </div>
  )
}
```

### Card grid
```tsx
<div className="grid grid-3 gap-4">
  {items.map(item => (
    <div key={item.id} className="card">
      <h3>{item.title}</h3>
      <p className="text-muted">{item.description}</p>
    </div>
  ))}
</div>
```

### Form with inputs
```tsx
<div className="card" style={{ maxWidth: 400 }}>
  <h2>Add Item</h2>
  <input placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
  <input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
  <button onClick={handleSubmit}>Submit</button>
</div>
```

### Stat display
```tsx
<div className="grid grid-4 gap-4">
  <div className="card text-center">
    <div className="text-muted">Users</div>
    <div style={{ fontSize: 32, fontWeight: 700, color: "var(--accent)" }}>1,234</div>
  </div>
</div>
```

### Tab navigation
```tsx
const [tab, setTab] = useState("overview")
<div className="flex gap-4 mb-4">
  {["overview", "details", "settings"].map(t => (
    <button key={t} onClick={() => setTab(t)}
      style={{ borderBottom: tab === t ? "2px solid var(--accent)" : "none" }}>
      {t}
    </button>
  ))}
</div>
{tab === "overview" && <Overview />}
{tab === "details" && <Details />}
```

### Modal/dialog
```tsx
{showModal && (
  <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
    <div className="card" style={{ maxWidth: 500, width: "100%" }}>
      <h2>Confirm</h2>
      <p>Are you sure?</p>
      <div className="flex gap-4">
        <button onClick={() => setShowModal(false)}>Cancel</button>
        <button onClick={handleConfirm} style={{ background: "var(--accent)", color: "#000" }}>Confirm</button>
      </div>
    </div>
  </div>
)}
```
