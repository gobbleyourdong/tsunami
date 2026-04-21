import http from "node:http"

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" })
    res.end(JSON.stringify({ ok: true }))
    return
  }
  res.writeHead(200, { "Content-Type": "text/plain" })
  res.end("stack web service — replace with your app\n")
})

const port = Number(process.env.PORT ?? 3000)
server.listen(port, () => {
  console.log(`listening on :${port}`)
})
