// Minimal ambient declarations so the model's Node-style timer typing compiles
// without pulling in @types/node. In the browser, `setInterval` / `setTimeout`
// return `number`, but the model habitually writes `NodeJS.Timeout` (Node.js
// convention) — `ReturnType<typeof setInterval>` is the correct runtime type.
declare namespace NodeJS {
  type Timeout = ReturnType<typeof setInterval>
  type Timer = ReturnType<typeof setInterval>
}
