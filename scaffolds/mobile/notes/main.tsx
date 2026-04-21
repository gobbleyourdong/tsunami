import { createRoot } from "react-dom/client"
import App from "./src/App"
import "./src/index.css"
import { registerServiceWorker } from "./src/lib/sw-register"

createRoot(document.getElementById("root")!).render(<App />)
registerServiceWorker()
