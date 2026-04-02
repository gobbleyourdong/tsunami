import React from "react"
import { createRoot } from "react-dom/client"
import App from "./App"
// Make React available globally — models often write React.FC without importing
;(window as any).React = React
createRoot(document.getElementById("root")!).render(<App />)
