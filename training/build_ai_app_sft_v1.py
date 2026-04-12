#!/usr/bin/env python3
"""build_ai_app_sft_v1.py — SFT training data for the ai-app-v1 adapter.

6 examples:
  AI01 — simple chatbot (project_init ai-app -> server/index.js -> App.tsx with useChat)
  AI02 — customer support bot with system prompt
  AI03 — code review assistant (code input + streaming review)
  AI04 — document summarizer (textarea + AI summary)
  AI05 — error recovery (npm missing dep -> file_edit)
  AI06 — conversational (add system prompt UI to existing chatbot)
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.build_v69 import SYSTEM_TEXT, TOOLS

OUT = Path("workspace/training_data/ai_app_sft_v1.jsonl")

def tc(tool_name, **kw):
    return {"role": "tool_call", "content": json.dumps({"name": tool_name, "parameters": kw})}

def tr(content):
    return {"role": "tool_result", "content": content}


# ── AI01: Simple chatbot ──────────────────────────────────────────────────────
def ai01_chatbot():
    return [
        {"role": "user", "content": "Build an AI chatbot interface."},
        tc("project_init", name="ai-chatbot", template="ai-app"),
        tr("Project 'ai-chatbot' ready (scaffold: ai-app) at workspace/deliverables/ai-chatbot\nDev server: http://localhost:5173\n\nThe scaffold includes:\n- server/index.js: Express SSE proxy (POST /api/chat)\n- src/hooks/useChat.ts: streaming hook\n- src/App.tsx: stub to replace"),
        tc("file_write", path="workspace/deliverables/ai-chatbot/src/App.tsx", content="""import { useState } from "react"
import { useChat } from "./hooks/useChat"

export default function App() {
  const { messages, sendMessage, isStreaming } = useChat()
  const [input, setInput] = useState("")

  function handleSend() {
    if (!input.trim() || isStreaming) return
    sendMessage(input.trim())
    setInput("")
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", maxWidth:700, margin:"0 auto", padding:16 }}>
      <h1 style={{ marginBottom:16, fontSize:20, fontWeight:700 }}>AI Chatbot</h1>
      <div style={{ flex:1, overflowY:"auto", display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
        {messages.length === 0 && (
          <p style={{ color:"#666", textAlign:"center", marginTop:80 }}>
            Start a conversation below.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            background: m.role === "user" ? "#2563eb" : "#f3f4f6",
            color: m.role === "user" ? "white" : "#111",
            borderRadius: 12, padding:"8px 14px", maxWidth:"75%", whiteSpace:"pre-wrap"
          }}>
            {m.content || (isStreaming && i === messages.length - 1 ? "▌" : "")}
          </div>
        ))}
      </div>
      <div style={{ display:"flex", gap:8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Type a message…"
          style={{ flex:1, padding:"10px 14px", borderRadius:8, border:"1px solid #ddd", fontSize:15 }}
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          style={{ padding:"10px 20px", borderRadius:8, background:"#2563eb", color:"white",
                   border:"none", cursor:"pointer", fontWeight:600 }}
        >
          Send
        </button>
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/ai-chatbot/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/ai-chatbot && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.2s — 312 modules transformed"),
        tc("undertow"),
        tr("Screenshot: clean chat UI, message bubbles on right (user, blue) and left (assistant, gray), send button, input bar. Streaming cursor visible."),
        tc("message_result", text="**AI Chatbot** is live.\n\nAdd your `OPENAI_API_KEY` to `.env` and start chatting. The `useChat` hook streams tokens as they arrive — no page refresh needed.\n\nTo customize:\n- Change the system prompt in `server/index.js`\n- Swap the model via `AI_MODEL=gpt-4o` in `.env`\n- Edit `src/App.tsx` for UI changes", done=True),
        tr("Message sent"),
    ]


# ── AI02: Customer support bot with system prompt ─────────────────────────────
def ai02_support_bot():
    return [
        {"role": "user", "content": "Build a customer support chatbot for an e-commerce store. It should know about our return policy (30-day returns, free shipping)."},
        tc("project_init", name="support-bot", template="ai-app"),
        tr("Project 'support-bot' ready (scaffold: ai-app) at workspace/deliverables/support-bot\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/support-bot/server/index.js", content="""import express from "express"
import cors from "cors"
import { config } from "dotenv"

config()

const app = express()
app.use(cors())
app.use(express.json())

const SYSTEM_PROMPT = `You are a friendly customer support agent for ShopCo, an e-commerce store.

Key policies:
- Returns: 30-day return window, no questions asked
- Shipping: Free shipping on all returns
- Refunds: Processed within 5-7 business days after we receive the item
- Exchanges: Available for size/color changes at no extra cost

Always be helpful, empathetic, and concise. If unsure, offer to escalate to a human agent.`

app.post("/api/chat", async (req, res) => {
  const { messages = [] } = req.body

  res.setHeader("Content-Type", "text/event-stream")
  res.setHeader("Cache-Control", "no-cache")
  res.setHeader("Connection", "keep-alive")

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: \`Bearer \${process.env.OPENAI_API_KEY}\`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.AI_MODEL || "gpt-4o-mini",
        messages: [{ role: "system", content: SYSTEM_PROMPT }, ...messages],
        stream: true,
      }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") { res.write("data: [DONE]\\n\\n"); break }
        try {
          const delta = JSON.parse(data).choices?.[0]?.delta?.content
          if (delta) res.write(\`data: \${JSON.stringify({ delta })}\\n\\n\`)
        } catch {}
      }
    }
  } catch (e) {
    res.write(\`data: \${JSON.stringify({ delta: \`[Error: \${e.message}]\` })}\\n\\n\`)
    res.write("data: [DONE]\\n\\n")
  }
  res.end()
})

app.listen(3001, () => console.log("Support bot proxy on :3001"))
"""),
        tr("File written: workspace/deliverables/support-bot/server/index.js"),
        tc("file_write", path="workspace/deliverables/support-bot/src/App.tsx", content="""import { useState } from "react"
import { useChat } from "./hooks/useChat"

export default function App() {
  const { messages, sendMessage, isStreaming } = useChat()
  const [input, setInput] = useState("")

  function handleSend() {
    if (!input.trim() || isStreaming) return
    sendMessage(input.trim())
    setInput("")
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", background:"#f8fafc" }}>
      {/* Header */}
      <div style={{ background:"#1e40af", color:"white", padding:"16px 24px", display:"flex", alignItems:"center", gap:12 }}>
        <div style={{ width:36, height:36, borderRadius:"50%", background:"#3b82f6", display:"flex", alignItems:"center", justifyContent:"center", fontSize:18 }}>🛍</div>
        <div>
          <div style={{ fontWeight:700, fontSize:16 }}>ShopCo Support</div>
          <div style={{ fontSize:12, opacity:0.8 }}>Typically replies instantly</div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:"auto", padding:24, display:"flex", flexDirection:"column", gap:12 }}>
        <div style={{ alignSelf:"flex-start", background:"white", borderRadius:12, padding:"10px 16px", maxWidth:"80%", boxShadow:"0 1px 3px rgba(0,0,0,0.1)" }}>
          Hi! I'm the ShopCo support assistant. How can I help you today?
        </div>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            background: m.role === "user" ? "#1e40af" : "white",
            color: m.role === "user" ? "white" : "#111",
            borderRadius: 12, padding:"10px 16px", maxWidth:"80%",
            boxShadow:"0 1px 3px rgba(0,0,0,0.1)", whiteSpace:"pre-wrap"
          }}>
            {m.content || (isStreaming && i === messages.length - 1 ? "▌" : "")}
          </div>
        ))}
      </div>

      {/* Input */}
      <div style={{ padding:16, background:"white", borderTop:"1px solid #e2e8f0", display:"flex", gap:8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Ask about returns, shipping, orders…"
          style={{ flex:1, padding:"10px 14px", borderRadius:24, border:"1px solid #cbd5e1", fontSize:14 }}
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          style={{ padding:"10px 18px", borderRadius:24, background:"#1e40af", color:"white",
                   border:"none", cursor:"pointer", fontWeight:600, fontSize:14 }}
        >
          Send
        </button>
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/support-bot/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/support-bot && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.4s"),
        tc("undertow"),
        tr("Screenshot: branded chat UI with ShopCo header (blue), initial greeting from bot, clean message bubbles, input bar."),
        tc("message_result", text="**ShopCo Support Bot** is live.\n\nThe system prompt encodes your return policy (30-day window, free return shipping, 5-7 day refunds). Customers can ask about returns, exchanges, or shipping and get instant answers.\n\nTo update policies, edit the `SYSTEM_PROMPT` constant in `server/index.js`.", done=True),
        tr("Message sent"),
    ]


# ── AI03: Code review assistant ───────────────────────────────────────────────
def ai03_code_review():
    return [
        {"role": "user", "content": "Build an AI code review tool. You paste code, it streams back a review."},
        tc("project_init", name="code-reviewer", template="ai-app"),
        tr("Project 'code-reviewer' ready (scaffold: ai-app) at workspace/deliverables/code-reviewer\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/code-reviewer/server/index.js", content="""import express from "express"
import cors from "cors"
import { config } from "dotenv"

config()
const app = express()
app.use(cors())
app.use(express.json({ limit: "1mb" }))

app.post("/api/review", async (req, res) => {
  const { code, language = "javascript" } = req.body

  res.setHeader("Content-Type", "text/event-stream")
  res.setHeader("Cache-Control", "no-cache")
  res.setHeader("Connection", "keep-alive")

  const systemPrompt = \`You are a senior software engineer. Review the provided \${language} code.
Focus on:
1. Bugs and logic errors
2. Security vulnerabilities
3. Performance issues
4. Code style and readability
5. Missing error handling

Format your review with clear headings and specific line references where applicable.\`

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: \`Bearer \${process.env.OPENAI_API_KEY}\`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.AI_MODEL || "gpt-4o-mini",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: \`Please review this code:\\n\\n\\\`\\\`\\\`\${language}\\n\${code}\\n\\\`\\\`\\\`\` }
        ],
        stream: true,
      }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") { res.write("data: [DONE]\\n\\n"); break }
        try {
          const delta = JSON.parse(data).choices?.[0]?.delta?.content
          if (delta) res.write(\`data: \${JSON.stringify({ delta })}\\n\\n\`)
        } catch {}
      }
    }
  } catch (e) {
    res.write(\`data: \${JSON.stringify({ delta: "[Error: " + e.message + "]" })}\\n\\n\`)
    res.write("data: [DONE]\\n\\n")
  }
  res.end()
})

app.listen(3001, () => console.log("Code review proxy on :3001"))
"""),
        tr("File written: workspace/deliverables/code-reviewer/server/index.js"),
        tc("file_write", path="workspace/deliverables/code-reviewer/src/App.tsx", content="""import { useState } from "react"

const LANGUAGES = ["javascript", "typescript", "python", "rust", "go", "java", "cpp"]

export default function App() {
  const [code, setCode] = useState("")
  const [language, setLanguage] = useState("javascript")
  const [review, setReview] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)

  async function handleReview() {
    if (!code.trim() || isStreaming) return
    setReview("")
    setIsStreaming(true)

    const res = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, language }),
    })
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const line of decoder.decode(value, { stream: true }).split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") break
        try {
          const { delta } = JSON.parse(data)
          if (delta) setReview(r => r + delta)
        } catch {}
      }
    }
    setIsStreaming(false)
  }

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", height:"100vh", gap:0 }}>
      {/* Left: Code input */}
      <div style={{ display:"flex", flexDirection:"column", borderRight:"1px solid #e2e8f0", background:"#1e1e2e" }}>
        <div style={{ padding:"12px 16px", borderBottom:"1px solid #333", display:"flex", alignItems:"center", gap:12, background:"#2a2a3e" }}>
          <span style={{ color:"#a0aec0", fontSize:14, fontWeight:600 }}>Code</span>
          <select
            value={language}
            onChange={e => setLanguage(e.target.value)}
            style={{ background:"#3a3a4e", color:"#e2e8f0", border:"1px solid #555", borderRadius:6, padding:"4px 8px", fontSize:13 }}
          >
            {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
          <button
            onClick={handleReview}
            disabled={isStreaming || !code.trim()}
            style={{ marginLeft:"auto", padding:"6px 16px", background:"#7c3aed", color:"white",
                     border:"none", borderRadius:6, cursor:"pointer", fontWeight:600, fontSize:13 }}
          >
            {isStreaming ? "Reviewing…" : "Review →"}
          </button>
        </div>
        <textarea
          value={code}
          onChange={e => setCode(e.target.value)}
          placeholder="Paste your code here…"
          style={{ flex:1, resize:"none", padding:16, background:"#1e1e2e", color:"#e2e8f0",
                   border:"none", outline:"none", fontFamily:"monospace", fontSize:13, lineHeight:1.6 }}
        />
      </div>

      {/* Right: Review output */}
      <div style={{ display:"flex", flexDirection:"column", background:"#f8fafc" }}>
        <div style={{ padding:"12px 16px", borderBottom:"1px solid #e2e8f0", background:"white" }}>
          <span style={{ fontSize:14, fontWeight:600, color:"#374151" }}>AI Review</span>
        </div>
        <div style={{ flex:1, overflowY:"auto", padding:20, fontFamily:"system-ui", fontSize:14,
                      lineHeight:1.7, color:"#374151", whiteSpace:"pre-wrap" }}>
          {review || (
            <p style={{ color:"#9ca3af", marginTop:60, textAlign:"center" }}>
              Paste code on the left and click Review →
            </p>
          )}
          {isStreaming && <span style={{ opacity:0.5 }}>▌</span>}
        </div>
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/code-reviewer/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/code-reviewer && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.3s"),
        tc("undertow"),
        tr("Screenshot: split panel — left side has dark code editor with language selector and Review button, right side shows streaming AI review text."),
        tc("message_result", text="**AI Code Reviewer** is live.\n\nSplit-panel layout: paste code on the left, get a streaming review on the right. Covers bugs, security, performance, style, and error handling.\n\nCustomize:\n- Add more languages to the `LANGUAGES` array in `App.tsx`\n- Adjust the review focus areas in the `systemPrompt` in `server/index.js`", done=True),
        tr("Message sent"),
    ]


# ── AI04: Document summarizer ─────────────────────────────────────────────────
def ai04_summarizer():
    return [
        {"role": "user", "content": "Build a document summarizer. User pastes a long document, AI streams back a concise summary."},
        tc("project_init", name="doc-summarizer", template="ai-app"),
        tr("Project 'doc-summarizer' ready (scaffold: ai-app) at workspace/deliverables/doc-summarizer\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/doc-summarizer/server/index.js", content="""import express from "express"
import cors from "cors"
import { config } from "dotenv"

config()
const app = express()
app.use(cors())
app.use(express.json({ limit: "5mb" }))

app.post("/api/summarize", async (req, res) => {
  const { text, style = "concise" } = req.body

  res.setHeader("Content-Type", "text/event-stream")
  res.setHeader("Cache-Control", "no-cache")
  res.setHeader("Connection", "keep-alive")

  const styleMap = {
    concise: "Provide a concise 2-3 paragraph summary capturing the main points.",
    bullets: "Provide a bulleted list of the 5-7 most important points.",
    executive: "Write a 1-paragraph executive summary suitable for a busy manager.",
  }

  const instruction = styleMap[style] || styleMap.concise

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: \`Bearer \${process.env.OPENAI_API_KEY}\`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.AI_MODEL || "gpt-4o-mini",
        messages: [
          { role: "system", content: \`You are an expert summarizer. \${instruction}\` },
          { role: "user", content: text.slice(0, 15000) }, // Safety limit
        ],
        stream: true,
      }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const raw = decoder.decode(value, { stream: true })
      for (const line of raw.split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") { res.write("data: [DONE]\\n\\n"); break }
        try {
          const delta = JSON.parse(data).choices?.[0]?.delta?.content
          if (delta) res.write(\`data: \${JSON.stringify({ delta })}\\n\\n\`)
        } catch {}
      }
    }
  } catch (e) {
    res.write(\`data: \${JSON.stringify({ delta: "[Error]" })}\\n\\n\`)
    res.write("data: [DONE]\\n\\n")
  }
  res.end()
})

app.listen(3001, () => console.log("Summarizer proxy on :3001"))
"""),
        tr("File written: workspace/deliverables/doc-summarizer/server/index.js"),
        tc("file_write", path="workspace/deliverables/doc-summarizer/src/App.tsx", content="""import { useState } from "react"

const STYLES = [
  { id: "concise", label: "Concise" },
  { id: "bullets", label: "Bullet Points" },
  { id: "executive", label: "Executive" },
]

export default function App() {
  const [text, setText] = useState("")
  const [style, setStyle] = useState("concise")
  const [summary, setSummary] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const wordCount = text.trim().split(/\\s+/).filter(Boolean).length

  async function handleSummarize() {
    if (!text.trim() || isStreaming) return
    setSummary("")
    setIsStreaming(true)

    const res = await fetch("/api/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style }),
    })
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const line of decoder.decode(value, { stream: true }).split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") break
        try {
          const { delta } = JSON.parse(data)
          if (delta) setSummary(s => s + delta)
        } catch {}
      }
    }
    setIsStreaming(false)
  }

  return (
    <div style={{ maxWidth:900, margin:"0 auto", padding:"32px 24px", fontFamily:"system-ui" }}>
      <h1 style={{ fontSize:24, fontWeight:700, marginBottom:4 }}>Document Summarizer</h1>
      <p style={{ color:"#6b7280", marginBottom:24, fontSize:14 }}>Paste any document and get an AI-powered summary in seconds.</p>

      <div style={{ display:"flex", gap:12, marginBottom:12, alignItems:"center" }}>
        <span style={{ fontSize:13, color:"#6b7280" }}>{wordCount.toLocaleString()} words</span>
        <div style={{ display:"flex", gap:4, marginLeft:"auto" }}>
          {STYLES.map(s => (
            <button key={s.id} onClick={() => setStyle(s.id)}
              style={{ padding:"5px 14px", borderRadius:20, border:"1px solid",
                       borderColor: style === s.id ? "#7c3aed" : "#d1d5db",
                       background: style === s.id ? "#7c3aed" : "white",
                       color: style === s.id ? "white" : "#374151",
                       fontSize:13, cursor:"pointer" }}>
              {s.label}
            </button>
          ))}
        </div>
        <button
          onClick={handleSummarize}
          disabled={isStreaming || !text.trim()}
          style={{ padding:"8px 20px", borderRadius:8, background:"#7c3aed", color:"white",
                   border:"none", cursor:"pointer", fontWeight:600, fontSize:14 }}
        >
          {isStreaming ? "Summarizing…" : "Summarize"}
        </button>
      </div>

      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Paste your document here…"
        style={{ width:"100%", height:240, padding:16, border:"1px solid #d1d5db", borderRadius:8,
                 fontSize:14, lineHeight:1.6, resize:"vertical", fontFamily:"inherit" }}
      />

      {(summary || isStreaming) && (
        <div style={{ marginTop:24, padding:20, background:"#f9fafb", borderRadius:8,
                      border:"1px solid #e5e7eb", fontSize:14, lineHeight:1.8, whiteSpace:"pre-wrap" }}>
          <div style={{ fontSize:12, fontWeight:600, color:"#6b7280", marginBottom:12, textTransform:"uppercase", letterSpacing:1 }}>
            Summary
          </div>
          {summary}
          {isStreaming && <span style={{ opacity:0.5 }}>▌</span>}
        </div>
      )}
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/doc-summarizer/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/doc-summarizer && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.3s"),
        tc("undertow"),
        tr("Screenshot: clean summarizer UI with word count, style toggle buttons (Concise/Bullet Points/Executive), large text area, and streaming summary below."),
        tc("message_result", text="**Document Summarizer** is live.\n\nThree summary styles: Concise, Bullet Points, Executive. Streams tokens as they arrive, handles up to ~15K characters safely.\n\nSet `OPENAI_API_KEY` in `.env` to activate.", done=True),
        tr("Message sent"),
    ]


# ── AI05: Error recovery ───────────────────────────────────────────────────────
def ai05_error_recovery():
    return [
        {"role": "user", "content": "Build an AI writing assistant."},
        tc("project_init", name="writing-assistant", template="ai-app"),
        tr("Project 'writing-assistant' ready (scaffold: ai-app) at workspace/deliverables/writing-assistant\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/writing-assistant/src/App.tsx", content="""import { useState } from "react"
import { useChat } from "./hooks/useChat"

const ACTIONS = [
  { label: "Improve", prompt: "Improve the writing style and clarity of:" },
  { label: "Shorten", prompt: "Make this more concise while keeping key points:" },
  { label: "Formalize", prompt: "Rewrite this in a formal, professional tone:" },
  { label: "Simplify", prompt: "Simplify this for a general audience:" },
]

export default function App() {
  const [text, setText] = useState("")
  const { messages, sendMessage, isStreaming } = useChat()

  async function handleAction(prompt: string) {
    if (!text.trim() || isStreaming) return
    sendMessage(prompt + "\\n\\n" + text)
  }

  const lastAssistant = messages.filter(m => m.role === "assistant").at(-1)

  return (
    <div style={{ maxWidth:800, margin:"0 auto", padding:"32px 24px", fontFamily:"system-ui" }}>
      <h1 style={{ fontSize:22, fontWeight:700, marginBottom:20 }}>AI Writing Assistant</h1>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Paste your text here…"
        style={{ width:"100%", height:180, padding:14, border:"1px solid #d1d5db",
                 borderRadius:8, fontSize:14, lineHeight:1.6, resize:"vertical" }}
      />
      <div style={{ display:"flex", gap:8, margin:"12px 0" }}>
        {ACTIONS.map(a => (
          <button key={a.label} onClick={() => handleAction(a.prompt)}
            disabled={isStreaming || !text.trim()}
            style={{ padding:"8px 18px", borderRadius:8, border:"1px solid #7c3aed",
                     background:"white", color:"#7c3aed", cursor:"pointer", fontWeight:600 }}>
            {a.label}
          </button>
        ))}
      </div>
      {(lastAssistant || isStreaming) && (
        <div style={{ padding:16, background:"#f9fafb", borderRadius:8, border:"1px solid #e5e7eb",
                      fontSize:14, lineHeight:1.8, whiteSpace:"pre-wrap" }}>
          {lastAssistant?.content || ""}
          {isStreaming && <span style={{ opacity:0.5 }}>▌</span>}
        </div>
      )}
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/writing-assistant/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/writing-assistant && npm run build 2>&1"),
        tr("Error: Cannot find module 'dotenv'\n  at node:internal/modules/cjs/loader:1147\nNode.js v22.0.0"),
        tc("file_edit", path="workspace/deliverables/writing-assistant/package.json", old="\"dotenv\": \"^16.4.0\"", new="\"dotenv\": \"^16.4.7\""),
        tr("File edited: workspace/deliverables/writing-assistant/package.json"),
        tc("shell_exec", command="cd workspace/deliverables/writing-assistant && npm install dotenv@latest 2>&1 | tail -3 && npm run build 2>&1 | tail -5"),
        tr("added 1 package in 3s\n✓ built in 1.2s"),
        tc("undertow"),
        tr("Screenshot: writing assistant with text area, four action buttons (Improve/Shorten/Formalize/Simplify), streaming result below."),
        tc("message_result", text="**AI Writing Assistant** is live.\n\nFour one-click actions: Improve, Shorten, Formalize, Simplify. Paste text → click action → streaming rewrite appears below.\n\nSet `OPENAI_API_KEY` in `.env` to activate.", done=True),
        tr("Message sent"),
    ]


# ── AI06: Conversational — add system prompt UI ─────────────────────────────
def ai06_conversational():
    return [
        {"role": "user", "content": "Build an AI chatbot."},
        tc("project_init", name="my-chatbot", template="ai-app"),
        tr("Project 'my-chatbot' ready (scaffold: ai-app) at workspace/deliverables/my-chatbot\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/my-chatbot/src/App.tsx", content="""import { useState } from "react"
import { useChat } from "./hooks/useChat"

export default function App() {
  const { messages, sendMessage, isStreaming, clearMessages } = useChat()
  const [input, setInput] = useState("")

  function handleSend() {
    if (!input.trim() || isStreaming) return
    sendMessage(input.trim())
    setInput("")
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", maxWidth:700, margin:"0 auto", padding:16 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <h1 style={{ fontSize:20, fontWeight:700 }}>AI Chat</h1>
        <button onClick={clearMessages} style={{ fontSize:13, color:"#6b7280", background:"none", border:"none", cursor:"pointer" }}>Clear</button>
      </div>
      <div style={{ flex:1, overflowY:"auto", display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            background: m.role === "user" ? "#2563eb" : "#f3f4f6",
            color: m.role === "user" ? "white" : "#111",
            borderRadius:12, padding:"8px 14px", maxWidth:"75%", whiteSpace:"pre-wrap"
          }}>
            {m.content || (isStreaming && i === messages.length - 1 ? "▌" : "")}
          </div>
        ))}
      </div>
      <div style={{ display:"flex", gap:8 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Message…"
          style={{ flex:1, padding:"10px 14px", borderRadius:8, border:"1px solid #ddd", fontSize:15 }}
        />
        <button onClick={handleSend} disabled={isStreaming || !input.trim()}
          style={{ padding:"10px 20px", borderRadius:8, background:"#2563eb", color:"white", border:"none", cursor:"pointer" }}>
          Send
        </button>
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/my-chatbot/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/my-chatbot && npm run build 2>&1 | tail -3"),
        tr("✓ built in 1.2s"),
        tc("undertow"),
        tr("Screenshot: clean chat UI live."),
        {"role": "user", "content": "Add a system prompt input field at the top so I can configure the bot's personality without touching code."},
        tc("file_write", path="workspace/deliverables/my-chatbot/server/index.js", content="""import express from "express"
import cors from "cors"
import { config } from "dotenv"

config()
const app = express()
app.use(cors())
app.use(express.json())

app.post("/api/chat", async (req, res) => {
  const { messages = [], systemPrompt } = req.body

  res.setHeader("Content-Type", "text/event-stream")
  res.setHeader("Cache-Control", "no-cache")
  res.setHeader("Connection", "keep-alive")

  const apiMessages = []
  if (systemPrompt?.trim()) {
    apiMessages.push({ role: "system", content: systemPrompt.trim() })
  }
  apiMessages.push(...messages)

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: \`Bearer \${process.env.OPENAI_API_KEY}\`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ model: process.env.AI_MODEL || "gpt-4o-mini", messages: apiMessages, stream: true }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const line of decoder.decode(value, { stream: true }).split("\\n")) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") { res.write("data: [DONE]\\n\\n"); break }
        try {
          const delta = JSON.parse(data).choices?.[0]?.delta?.content
          if (delta) res.write(\`data: \${JSON.stringify({ delta })}\\n\\n\`)
        } catch {}
      }
    }
  } catch (e) {
    res.write(\`data: \${JSON.stringify({ delta: "[Error]" })}\\n\\n\`)
    res.write("data: [DONE]\\n\\n")
  }
  res.end()
})

app.listen(3001, () => console.log("Chat proxy on :3001"))
"""),
        tr("File written: workspace/deliverables/my-chatbot/server/index.js"),
        tc("file_write", path="workspace/deliverables/my-chatbot/src/App.tsx", content="""import { useState } from "react"
import { useChat } from "./hooks/useChat"

export default function App() {
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful AI assistant.")
  const [editingSystem, setEditingSystem] = useState(false)
  const { messages, sendMessage, isStreaming, clearMessages } = useChat(systemPrompt)
  const [input, setInput] = useState("")

  function handleSend() {
    if (!input.trim() || isStreaming) return
    sendMessage(input.trim())
    setInput("")
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", maxWidth:700, margin:"0 auto", padding:16 }}>
      {/* System prompt editor */}
      <div style={{ background:"#f9fafb", border:"1px solid #e5e7eb", borderRadius:8, padding:12, marginBottom:12 }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom: editingSystem ? 8 : 0 }}>
          <span style={{ fontSize:12, fontWeight:600, color:"#6b7280", textTransform:"uppercase", letterSpacing:0.5 }}>System Prompt</span>
          <button onClick={() => setEditingSystem(!editingSystem)}
            style={{ fontSize:12, color:"#2563eb", background:"none", border:"none", cursor:"pointer" }}>
            {editingSystem ? "Done" : "Edit"}
          </button>
        </div>
        {editingSystem ? (
          <textarea
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            rows={3}
            style={{ width:"100%", padding:8, border:"1px solid #d1d5db", borderRadius:6, fontSize:13, resize:"vertical" }}
          />
        ) : (
          <p style={{ fontSize:13, color:"#374151", margin:0, marginTop:4 }}>{systemPrompt}</p>
        )}
      </div>

      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
        <h1 style={{ fontSize:18, fontWeight:700 }}>AI Chat</h1>
        <button onClick={clearMessages} style={{ fontSize:13, color:"#6b7280", background:"none", border:"none", cursor:"pointer" }}>Clear</button>
      </div>

      <div style={{ flex:1, overflowY:"auto", display:"flex", flexDirection:"column", gap:8, marginBottom:12 }}>
        {messages.length === 0 && (
          <p style={{ color:"#9ca3af", textAlign:"center", marginTop:60, fontSize:14 }}>Start chatting below</p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            background: m.role === "user" ? "#2563eb" : "#f3f4f6",
            color: m.role === "user" ? "white" : "#111",
            borderRadius:12, padding:"8px 14px", maxWidth:"75%", whiteSpace:"pre-wrap"
          }}>
            {m.content || (isStreaming && i === messages.length - 1 ? "▌" : "")}
          </div>
        ))}
      </div>

      <div style={{ display:"flex", gap:8 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Message…"
          style={{ flex:1, padding:"10px 14px", borderRadius:8, border:"1px solid #ddd", fontSize:15 }}
        />
        <button onClick={handleSend} disabled={isStreaming || !input.trim()}
          style={{ padding:"10px 20px", borderRadius:8, background:"#2563eb", color:"white", border:"none", cursor:"pointer" }}>
          Send
        </button>
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/my-chatbot/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/my-chatbot && npm run build 2>&1 | tail -3"),
        tr("✓ built in 1.2s"),
        tc("undertow"),
        tr("Screenshot: chat UI with collapsible system prompt panel at top showing 'You are a helpful AI assistant.' with Edit button. Rest of UI unchanged."),
        tc("message_result", text="Added a **system prompt panel** at the top. Click Edit to change the bot's personality on the fly — no code changes needed.\n\nThe `useChat(systemPrompt)` hook passes it to the server with every request, so the bot immediately adopts the new persona on the next message.", done=True),
        tr("Message sent"),
    ]


def build_example(source_fn, messages):
    text = f"<start_of_turn>system\n{SYSTEM_TEXT}<end_of_turn>\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            text += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role in ("assistant", "tool_call", "tool_result"):
            text += f"<start_of_turn>model\n{content}<end_of_turn>\n"
    return {"text": text, "source": source_fn}


def main():
    examples_raw = [
        ("ai01_chatbot", ai01_chatbot()),
        ("ai02_support_bot", ai02_support_bot()),
        ("ai03_code_review", ai03_code_review()),
        ("ai04_summarizer", ai04_summarizer()),
        ("ai05_error_recovery", ai05_error_recovery()),
        ("ai06_conversational", ai06_conversational()),
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for source, msgs in examples_raw:
            obj = build_example(source, msgs)
            f.write(json.dumps(obj) + "\n")
            char_count = len(obj["text"])
            print(f"  {source}: {len(msgs)} msgs -> {char_count} chars")

    print(f"\nTotal: {len(examples_raw)} examples")
    print(f"Wrote to {OUT}")


if __name__ == "__main__":
    main()
