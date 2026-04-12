import express from "express"
import cors from "cors"
import { config } from "dotenv"

config()

const app = express()
app.use(cors())
app.use(express.json())

const PORT = process.env.PORT || 3001

/**
 * POST /api/chat
 * Body: { messages: [{role, content}], systemPrompt?: string }
 * Streams SSE: data: {"delta":"token"}\n\n ... data: [DONE]\n\n
 *
 * Replace the fetch below with your preferred LLM provider.
 * Default: OpenAI-compatible endpoint (works with OpenAI, Together, Groq, etc.)
 */
app.post("/api/chat", async (req, res) => {
  const { messages = [], systemPrompt } = req.body

  res.setHeader("Content-Type", "text/event-stream")
  res.setHeader("Cache-Control", "no-cache")
  res.setHeader("Connection", "keep-alive")

  const apiMessages = []
  if (systemPrompt) apiMessages.push({ role: "system", content: systemPrompt })
  apiMessages.push(...messages)

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.AI_MODEL || "gpt-4o-mini",
        messages: apiMessages,
        stream: true,
      }),
    })

    if (!response.ok) {
      const err = await response.text()
      res.write(`data: ${JSON.stringify({ delta: `[Error: ${response.status}]` })}\n\n`)
      res.write("data: [DONE]\n\n")
      res.end()
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split("\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") {
          res.write("data: [DONE]\n\n")
          break
        }
        try {
          const chunk = JSON.parse(data)
          const delta = chunk.choices?.[0]?.delta?.content
          if (delta) res.write(`data: ${JSON.stringify({ delta })}\n\n`)
        } catch { /* skip malformed */ }
      }
    }
  } catch (e) {
    res.write(`data: ${JSON.stringify({ delta: `[Server error: ${e.message}]` })}\n\n`)
    res.write("data: [DONE]\n\n")
  }

  res.end()
})

app.listen(PORT, () => console.log(`AI proxy on :${PORT} — set OPENAI_API_KEY in .env`))
