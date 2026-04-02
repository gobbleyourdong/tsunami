import React from "react"
;(window as any).React = React
import "./index.css"
import { createRoot } from "react-dom/client"
import App from "./App"
createRoot(document.getElementById("root")!).render(<App />)
