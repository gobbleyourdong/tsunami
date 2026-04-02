import React from "react"
;(window as any).React = React
import { createRoot } from "react-dom/client"
import "./index.css"
import App from "./App"
createRoot(document.getElementById("root")!).render(<App />)
