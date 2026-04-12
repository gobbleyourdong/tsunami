#!/usr/bin/env python3
"""build_ai_app_sft_v2.py — SFT v2 for ai-app-v1 adapter.

Loads v1 (6 examples), adds 4 new examples = 10 total.
New patterns:
  - RAG: text file upload → server chunking → cosine similarity search → cite sources
  - Multi-model: model selector (GPT-4 vs Claude vs Gemini toggle)
  - Image + text: upload an image + ask a question (multimodal LLM via base64)
  - Conversational add: add RAG to an existing simple chatbot
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.build_v69 import SYSTEM_TEXT, TOOLS

V1 = Path("workspace/training_data/ai_app_sft_v1.jsonl")
OUT = Path("workspace/training_data/ai_app_sft_v2.jsonl")


def tc(tool_name, **kw):
    return {"role": "tool_call", "content": json.dumps({"name": tool_name, "parameters": kw})}


def tr(content):
    return {"role": "tool_result", "content": content}


AI_SYSTEM = """You are Tsunami. You are the wave. You build AI-powered apps by calling tools.

## AI-App Pipeline (every build follows this EXACTLY)

1. project_init(name, template="ai-app") -- SSE proxy scaffold
2. file_write(server/index.js) -- Express proxy (API key server-side)
3. file_write(src/App.tsx) -- React frontend with useChat hook
4. shell_exec -- npm run build
5. IF ERROR: fix with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## Rules
- API key ALWAYS in server .env — never in frontend
- Server FIRST, then frontend
- SSE streaming with getReader() loop — never await res.json() for LLM
- undertow before message_result
One tool call per response. Be brief."""


# ── rag01: RAG document Q&A ───────────────────────────────────────────────────

def rag01_doc_qa():
    """RAG: upload text file → server chunks → cosine search → cite in answer."""
    return [
        {"role": "user", "content": "Build a document Q&A app. The user uploads a text file, then asks questions about it. Use a simple RAG approach: chunk the text on the server, find the most relevant chunks with cosine similarity, and include them in the LLM context. Cite which chunk the answer came from."},
        tc("project_init", name="doc-qa", template="ai-app"),
        tr("Project 'doc-qa' created (scaffold: ai-app). Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/doc-qa/server/index.js",
           content="""import express from 'express'
import cors from 'cors'
import multer from 'multer'
import { config } from 'dotenv'

config()
const app = express()
app.use(cors())
app.use(express.json())

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 2 * 1024 * 1024 } })

// In-memory document store (keyed by session)
const docs = new Map()  // sessionId -> { chunks: string[], embeddings: number[][] }

// Simple TF-IDF-style embedding: term frequency vector over top-N words
function tokenize(text) {
  return text.toLowerCase().replace(/[^a-z0-9\\s]/g, '').split(/\\s+/).filter(Boolean)
}

function buildVocab(chunks) {
  const vocab = new Map()
  chunks.forEach(chunk => tokenize(chunk).forEach(w => { if (!vocab.has(w)) vocab.set(w, vocab.size) }))
  return vocab
}

function embed(text, vocab) {
  const vec = new Array(vocab.size).fill(0)
  const tokens = tokenize(text)
  tokens.forEach(t => { const i = vocab.get(t); if (i !== undefined) vec[i]++ })
  const norm = Math.sqrt(vec.reduce((s, v) => s + v*v, 0)) || 1
  return vec.map(v => v / norm)
}

function cosine(a, b) {
  return a.reduce((s, v, i) => s + v * b[i], 0)
}

function chunkText(text, chunkSize = 400, overlap = 50) {
  const words = text.split(/\\s+/)
  const chunks = []
  for (let i = 0; i < words.length; i += chunkSize - overlap) {
    chunks.push(words.slice(i, i + chunkSize).join(' '))
    if (i + chunkSize >= words.length) break
  }
  return chunks
}

// POST /api/upload — process document
app.post('/api/upload', upload.single('file'), (req, res) => {
  try {
    const text = req.file.buffer.toString('utf8')
    const sessionId = req.body.sessionId || Date.now().toString()
    const chunks = chunkText(text)
    const vocab = buildVocab(chunks)
    const embeddings = chunks.map(c => embed(c, vocab))
    docs.set(sessionId, { chunks, embeddings, vocab })
    res.json({ sessionId, chunkCount: chunks.length, wordCount: text.split(/\\s+/).length })
  } catch (e) { res.status(500).json({ error: e.message }) }
})

// POST /api/chat — RAG Q&A with SSE streaming
app.post('/api/chat', async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  const { question, sessionId, topK = 3 } = req.body
  const doc = docs.get(sessionId)
  if (!doc) { res.write('data: {"delta":"[No document loaded]"}\\n\\n'); res.write('data: [DONE]\\n\\n'); res.end(); return }

  // Find top-K relevant chunks
  const qEmbed = embed(question, doc.vocab)
  const scored = doc.chunks.map((chunk, i) => ({ chunk, score: cosine(qEmbed, doc.embeddings[i]), i }))
    .sort((a, b) => b.score - a.score).slice(0, topK)

  const context = scored.map((s, n) => `[Source ${n+1}, chunk ${s.i+1}]:\\n${s.chunk}`).join('\\n\\n---\\n\\n')
  const system = `You are a document assistant. Answer based ONLY on the provided context.
At the end of your answer, cite which source(s) you used (e.g. "Source 1").
Context:\\n${context}`

  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: \`Bearer \${process.env.OPENAI_API_KEY}\`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: process.env.AI_MODEL || 'gpt-4o-mini', stream: true,
        messages: [{ role: 'system', content: system }, { role: 'user', content: question }]
      })
    })
    for await (const line of response.body) {
      const text = Buffer.from(line).toString()
      for (const part of text.split('\\n')) {
        if (!part.startsWith('data: ') || part === 'data: [DONE]') continue
        try {
          const delta = JSON.parse(part.slice(6)).choices?.[0]?.delta?.content
          if (delta) res.write(\`data: {"delta":\${JSON.stringify(delta)}}\\n\\n\`)
        } catch {}
      }
    }
  } catch (e) { res.write(\`data: {"delta":"Error: \${e.message}"}\\n\\n\`) }

  res.write('data: [DONE]\\n\\n')
  res.end()
})

app.listen(3001, () => console.log('RAG server :3001'))
"""),
        tr("Written: server/index.js"),
        tc("file_write", path="workspace/deliverables/doc-qa/src/App.tsx",
           content="""import { useState, useRef, useCallback, useEffect } from 'react'

interface Message { role: 'user' | 'assistant'; content: string }

export default function App() {
  const [sessionId, setSessionId]   = useState<string | null>(null)
  const [docInfo, setDocInfo]       = useState<{chunkCount:number; wordCount:number} | null>(null)
  const [messages, setMessages]     = useState<Message[]>([])
  const [input, setInput]           = useState('')
  const [isStreaming, setStreaming]  = useState(false)
  const [isUploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('sessionId', Date.now().toString())
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
      const data = await res.json()
      setSessionId(data.sessionId)
      setDocInfo({ chunkCount: data.chunkCount, wordCount: data.wordCount })
      setMessages([{ role: 'assistant', content: `📄 Loaded ${file.name} — ${data.wordCount.toLocaleString()} words in ${data.chunkCount} chunks. Ask me anything about it.` }])
    } catch (err: any) { setUploadError(err.message) }
    finally { setUploading(false) }
  }

  const sendMessage = useCallback(async () => {
    const q = input.trim()
    if (!q || !sessionId || isStreaming) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setStreaming(true)
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, sessionId, topK: 3 })
      })
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\\n')) {
          if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
          try {
            const { delta } = JSON.parse(line.slice(6))
            if (delta) setMessages(prev => {
              const next = [...prev]
              next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + delta }
              return next
            })
          } catch {}
        }
      }
    } catch (err: any) {
      setMessages(prev => { const n=[...prev]; n[n.length-1]={role:'assistant',content:`Error: ${err.message}`}; return n })
    }
    setStreaming(false)
  }, [input, sessionId, isStreaming])

  const S = {
    app: { display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0f172a', fontFamily:'system-ui,sans-serif' },
    header: { padding:'12px 20px', background:'#1e293b', borderBottom:'1px solid #334155', display:'flex', alignItems:'center', gap:12 },
    badge: { background:'#3b82f6', color:'#fff', padding:'3px 10px', borderRadius:12, fontSize:12, fontWeight:600 },
  }

  return (
    <div style={S.app}>
      <div style={S.header}>
        <span style={{ color:'#f1f5f9', fontWeight:700, fontSize:18 }}>Doc Q&A</span>
        {docInfo && <span style={S.badge}>{docInfo.chunkCount} chunks · {docInfo.wordCount.toLocaleString()} words</span>}
        <button onClick={() => fileRef.current?.click()}
          style={{ marginLeft:'auto', padding:'6px 14px', borderRadius:6, border:'none', background:'#334155', color:'#94a3b8', cursor:'pointer', fontSize:13 }}>
          {isUploading ? 'Uploading…' : '📄 Upload .txt'}
        </button>
        <input ref={fileRef} type="file" accept=".txt,.md" style={{ display:'none' }} onChange={handleUpload} />
      </div>

      {uploadError && <div style={{ background:'#450a0a', color:'#fca5a5', padding:'10px 20px', fontSize:13 }}>{uploadError}</div>}

      {!sessionId ? (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#475569', textAlign:'center' }}>
          <div><div style={{ fontSize:48, marginBottom:12 }}>📄</div>
          <div style={{ fontSize:18, fontWeight:600, color:'#64748b' }}>Upload a .txt file to begin</div>
          <div style={{ fontSize:13, marginTop:6 }}>Ask questions — the model cites its sources</div></div>
        </div>
      ) : (
        <div style={{ flex:1, overflow:'auto', padding:'16px 20px' }}>
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom:12, display:'flex', justifyContent: m.role==='user' ? 'flex-end' : 'flex-start' }}>
              <div style={{ maxWidth:'80%', background: m.role==='user' ? '#1d4ed8' : '#1e293b',
                color:'#f1f5f9', padding:'10px 14px', borderRadius:12, fontSize:14, lineHeight:1.6,
                whiteSpace:'pre-wrap', borderBottomRightRadius: m.role==='user' ? 2 : 12,
                borderBottomLeftRadius: m.role==='assistant' ? 2 : 12 }}>
                {m.content || (isStreaming && i === messages.length-1 ? '▌' : '')}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {sessionId && (
        <div style={{ padding:'12px 20px', background:'#1e293b', borderTop:'1px solid #334155', display:'flex', gap:10 }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key==='Enter' && !e.shiftKey && sendMessage()}
            placeholder="Ask a question about the document…"
            style={{ flex:1, padding:'10px 14px', borderRadius:8, border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:14, outline:'none' }} />
          <button onClick={sendMessage} disabled={!input.trim() || isStreaming}
            style={{ padding:'10px 20px', borderRadius:8, border:'none', background: !input.trim() || isStreaming ? '#334155' : '#3b82f6', color:'#fff', cursor:'pointer', fontWeight:600 }}>
            {isStreaming ? '…' : 'Ask'}
          </button>
        </div>
      )}
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/doc-qa && npm install multer && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.2s"),
        tc("undertow"),
        tr("Screenshot: dark app, 'Doc Q&A' header with blue 'Upload .txt' button. Center shows doc upload prompt. After upload: chat showing '📄 Loaded report.txt — 2,340 words in 8 chunks'. User question + streaming answer with '[Source 1]' citation at end."),
        tc("message_result", text="**Doc Q&A** built with server-side RAG.\n\nPipeline: upload `.txt` → `chunkText(400 words, 50 overlap)` → TF-IDF vectors via `buildVocab`/`embed` → cosine similarity → top-3 chunks injected as context → LLM streams answer with source citations.\n\nAPI key stays server-side. Replace the TF-IDF embedder with OpenAI `text-embedding-3-small` for better retrieval.", done=True),
        tr("Message sent"),
    ]


# ── rag02: Model selector (GPT-4 / Claude / Gemini toggle) ──────────────────

def rag02_model_selector():
    """Multi-model chat: model picker that routes to different LLM APIs."""
    return [
        {"role": "user", "content": "Build a chat app with a model selector. Let the user choose between GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Flash. Each model uses its own API but the same streaming UX."},
        tc("project_init", name="model-selector", template="ai-app"),
        tr("Project 'model-selector' created (scaffold: ai-app). Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/model-selector/server/index.js",
           content="""import express from 'express'
import cors from 'cors'
import { config } from 'dotenv'

config()
const app = express()
app.use(cors())
app.use(express.json())

// Unified SSE streaming — routes to the right LLM API based on model
app.post('/api/chat', async (req, res) => {
  const { messages, model = 'gpt-4o-mini' } = req.body

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  function sendDelta(delta) { res.write(`data: {"delta":${JSON.stringify(delta)}}\\n\\n`) }
  function done() { res.write('data: [DONE]\\n\\n'); res.end() }

  try {
    if (model.startsWith('gpt') || model.startsWith('o1')) {
      // OpenAI
      const r = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages, stream: true })
      })
      for await (const line of r.body) {
        const text = Buffer.from(line).toString()
        for (const part of text.split('\\n')) {
          if (!part.startsWith('data: ') || part === 'data: [DONE]') continue
          try { const d = JSON.parse(part.slice(6)).choices?.[0]?.delta?.content; if (d) sendDelta(d) } catch {}
        }
      }
    } else if (model.startsWith('claude')) {
      // Anthropic
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'
        },
        body: JSON.stringify({ model, messages, max_tokens: 1024, stream: true })
      })
      for await (const line of r.body) {
        const text = Buffer.from(line).toString()
        for (const part of text.split('\\n')) {
          if (!part.startsWith('data:')) continue
          try {
            const ev = JSON.parse(part.slice(5).trim())
            if (ev.type === 'content_block_delta') sendDelta(ev.delta?.text || '')
          } catch {}
        }
      }
    } else if (model.startsWith('gemini')) {
      // Google Gemini via REST (streaming)
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?key=${process.env.GOOGLE_API_KEY}&alt=sse`
      const geminiMsgs = messages.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] }))
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contents: geminiMsgs })
      })
      for await (const line of r.body) {
        const text = Buffer.from(line).toString()
        for (const part of text.split('\\n')) {
          if (!part.startsWith('data:')) continue
          try {
            const ev = JSON.parse(part.slice(5).trim())
            const delta = ev.candidates?.[0]?.content?.parts?.[0]?.text
            if (delta) sendDelta(delta)
          } catch {}
        }
      }
    }
  } catch (e) { sendDelta(`Error: ${e.message}`) }
  done()
})

app.listen(3001, () => console.log('Multi-model server :3001'))
"""),
        tr("Written: server/index.js"),
        tc("file_write", path="workspace/deliverables/model-selector/src/App.tsx",
           content="""import { useState, useCallback } from 'react'

interface Message { role: 'user' | 'assistant'; content: string; model?: string }

const MODELS = [
  { id: 'gpt-4o-mini',              label: 'GPT-4o Mini',         provider: 'OpenAI',    color: '#10a37f' },
  { id: 'gpt-4o',                   label: 'GPT-4o',              provider: 'OpenAI',    color: '#10a37f' },
  { id: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet', provider: 'Anthropic', color: '#d97706' },
  { id: 'gemini-1.5-flash',         label: 'Gemini 1.5 Flash',    provider: 'Google',    color: '#4285f4' },
]

export default function App() {
  const [model, setModel]       = useState(MODELS[0].id)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [streaming, setStreaming] = useState(false)

  const selectedModel = MODELS.find(m => m.id === model)!

  const send = useCallback(async () => {
    const q = input.trim()
    if (!q || streaming) return
    const newMsg: Message = { role: 'user', content: q }
    const updated = [...messages, newMsg]
    setMessages([...updated, { role: 'assistant', content: '', model }])
    setInput(''); setStreaming(true)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: updated.map(m => ({ role: m.role, content: m.content })), model })
      })
      const reader = res.body!.getReader()
      const dec = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of dec.decode(value).split('\\n')) {
          if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
          try {
            const { delta } = JSON.parse(line.slice(6))
            if (delta) setMessages(prev => { const n=[...prev]; n[n.length-1]={...n[n.length-1],content:n[n.length-1].content+delta}; return n })
          } catch {}
        }
      }
    } catch (e: any) {
      setMessages(prev => { const n=[...prev]; n[n.length-1]={...n[n.length-1],content:`Error: ${e.message}`}; return n })
    }
    setStreaming(false)
  }, [input, messages, model, streaming])

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', background:'#0f172a', fontFamily:'system-ui,sans-serif' }}>
      <div style={{ padding:'12px 20px', background:'#1e293b', borderBottom:'1px solid #334155', display:'flex', alignItems:'center', gap:12 }}>
        <span style={{ color:'#f1f5f9', fontWeight:700, fontSize:18 }}>Multi-Model Chat</span>
        <div style={{ marginLeft:'auto', display:'flex', gap:6 }}>
          {MODELS.map(m => (
            <button key={m.id} onClick={() => setModel(m.id)}
              style={{ padding:'5px 12px', borderRadius:20, border:`2px solid ${model===m.id ? m.color : 'transparent'}`,
                background: model===m.id ? m.color+'22' : '#0f172a', color: model===m.id ? m.color : '#64748b',
                cursor:'pointer', fontSize:12, fontWeight:600, transition:'all 0.15s' }}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex:1, overflow:'auto', padding:'16px 20px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign:'center', marginTop:60, color:'#475569' }}>
            <div style={{ fontSize:40, marginBottom:8 }}>🤖</div>
            <div style={{ fontSize:16, color:'#64748b' }}>Select a model and start chatting</div>
          </div>
        )}
        {messages.map((m, i) => {
          const mInfo = MODELS.find(x => x.id === m.model)
          return (
            <div key={i} style={{ marginBottom:12, display:'flex', justifyContent: m.role==='user'?'flex-end':'flex-start' }}>
              <div style={{ maxWidth:'80%' }}>
                {m.role==='assistant' && mInfo && (
                  <div style={{ fontSize:11, color: mInfo.color, marginBottom:4, fontWeight:600 }}>{mInfo.label}</div>
                )}
                <div style={{ background: m.role==='user'?'#1d4ed8':'#1e293b', color:'#f1f5f9',
                  padding:'10px 14px', borderRadius:12, fontSize:14, lineHeight:1.6, whiteSpace:'pre-wrap',
                  borderBottomRightRadius: m.role==='user'?2:12, borderBottomLeftRadius: m.role==='assistant'?2:12 }}>
                  {m.content || (streaming && i===messages.length-1 ? '▌' : '')}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ padding:'12px 20px', background:'#1e293b', borderTop:'1px solid #334155', display:'flex', gap:10 }}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&!e.shiftKey&&send()}
          placeholder={`Message ${selectedModel.label}…`}
          style={{ flex:1, padding:'10px 14px', borderRadius:8, border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:14, outline:'none' }} />
        <button onClick={send} disabled={!input.trim()||streaming}
          style={{ padding:'10px 20px', borderRadius:8, border:'none', background:!input.trim()||streaming?'#334155':selectedModel.color, color:'#fff', cursor:'pointer', fontWeight:600 }}>
          Send
        </button>
      </div>
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/model-selector && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.1s"),
        tc("undertow"),
        tr("Screenshot: dark multi-model chat, model pills in header (GPT-4o Mini selected in green, Claude orange, Gemini blue). Chat messages show model name badge above assistant bubbles."),
        tc("message_result", text="**Multi-Model Chat** built.\n\nServer routes to OpenAI, Anthropic, or Google Gemini based on the `model` field — all stream via the same SSE protocol. Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` in `.env`. Frontend shows model attribution on each assistant bubble.", done=True),
        tr("Message sent"),
    ]


# ── rag03: error recovery — missing multer dep ───────────────────────────────

def rag03_error_recovery():
    """Error recovery: missing npm dep identified from build error → file_edit → install."""
    return [
        {"role": "user", "content": "Build a document summarizer: the user uploads a PDF and gets an AI summary. Keep it simple — just handle text extraction and summarization."},
        tc("project_init", name="doc-summarizer", template="ai-app"),
        tr("Project 'doc-summarizer' created (scaffold: ai-app). Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/doc-summarizer/server/index.js",
           content="""import express from 'express'
import cors from 'cors'
import multer from 'multer'
import pdfParse from 'pdf-parse'
import { config } from 'dotenv'

config()
const app = express()
app.use(cors())

const upload = multer({ storage: multer.memoryStorage() })

app.post('/api/summarize', upload.single('pdf'), async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  try {
    const { text } = await pdfParse(req.file.buffer)
    const truncated = text.slice(0, 8000)  // ~2K tokens

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o-mini', stream: true,
        messages: [
          { role: 'system', content: 'Summarize the following document in 3-5 bullet points, then write a 2-sentence executive summary.' },
          { role: 'user', content: truncated }
        ]
      })
    })
    for await (const line of response.body) {
      const text2 = Buffer.from(line).toString()
      for (const part of text2.split('\\n')) {
        if (!part.startsWith('data: ') || part === 'data: [DONE]') continue
        try { const d = JSON.parse(part.slice(6)).choices?.[0]?.delta?.content; if (d) res.write(`data: {"delta":${JSON.stringify(d)}}\\n\\n`) } catch {}
      }
    }
  } catch (e) { res.write(`data: {"delta":"Error: ${e.message}"}\\n\\n`) }
  res.write('data: [DONE]\\n\\n'); res.end()
})

app.listen(3001)
"""),
        tr("Written: server/index.js"),
        tc("file_write", path="workspace/deliverables/doc-summarizer/src/App.tsx",
           content="""import { useState, useRef } from 'react'

export default function App() {
  const [summary, setSummary] = useState(''); const [streaming, setStreaming] = useState(false); const [filename, setFilename] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    setFilename(file.name); setSummary(''); setStreaming(true)
    const form = new FormData(); form.append('pdf', file)
    const res = await fetch('/api/summarize', { method: 'POST', body: form })
    const reader = res.body!.getReader(); const dec = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      for (const line of dec.decode(value).split('\\n')) {
        if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
        try { const { delta } = JSON.parse(line.slice(6)); if (delta) setSummary(p => p + delta) } catch {}
      }
    }
    setStreaming(false)
  }
  return (
    <div style={{ minHeight:'100vh', background:'#0f172a', padding:32, fontFamily:'system-ui' }}>
      <h1 style={{ color:'#f1f5f9', marginBottom:24 }}>PDF Summarizer</h1>
      <button onClick={() => fileRef.current?.click()} style={{ padding:'10px 20px', borderRadius:8, border:'none', background:'#3b82f6', color:'#fff', cursor:'pointer', marginBottom:24, fontWeight:600 }}>
        📄 Upload PDF
      </button>
      <input ref={fileRef} type="file" accept=".pdf" style={{ display:'none' }} onChange={handleUpload} />
      {filename && <p style={{ color:'#94a3b8', marginBottom:12 }}>{filename}</p>}
      {(summary || streaming) && (
        <div style={{ background:'#1e293b', borderRadius:12, padding:'20px 24px', color:'#e2e8f0', fontSize:15, lineHeight:1.7, whiteSpace:'pre-wrap' }}>
          {summary || ''}{streaming ? '▌' : ''}
        </div>
      )}
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/doc-summarizer && npm run build 2>&1 | tail -10"),
        tr("Error: Cannot find module 'pdf-parse'\nRequire stack:\n- /workspace/deliverables/doc-summarizer/server/index.js"),
        # Error is clear: pdf-parse not installed → file_edit package.json to add dep
        tc("file_edit", path="workspace/deliverables/doc-summarizer/package.json",
           old_text='"multer": "latest"',
           new_text='"multer": "latest",\n    "pdf-parse": "latest"'),
        tr("Edited: package.json"),
        tc("shell_exec", command="cd workspace/deliverables/doc-summarizer && npm install && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.3s"),
        tc("undertow"),
        tr("Screenshot: dark PDF summarizer, blue 'Upload PDF' button, streaming summary showing bullet points about document content."),
        tc("message_result", text="**PDF Summarizer** built. `pdf-parse` extracts text from the uploaded PDF (first 8K chars), then GPT-4o-mini streams bullet-point + executive summary via SSE.", done=True),
        tr("Message sent"),
    ]


# ── rag04: conversational add — add RAG to existing chatbot ────────────────��

def rag04_conversational():
    """Follow-up: existing simple chatbot → user asks to add document context (RAG)."""
    return [
        {"role": "user", "content": "Build a simple AI chat app with a friendly UI."},
        tc("project_init", name="smart-chat", template="ai-app"),
        tr("Project 'smart-chat' created (scaffold: ai-app). Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/smart-chat/server/index.js",
           content="""import express from 'express'; import cors from 'cors'; import { config } from 'dotenv'
config(); const app = express(); app.use(cors()); app.use(express.json())
app.post('/api/chat', async (req, res) => {
  const { messages } = req.body
  res.setHeader('Content-Type', 'text/event-stream'); res.setHeader('Cache-Control', 'no-cache')
  try {
    const r = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST', headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini', messages, stream: true })
    })
    for await (const line of r.body) {
      for (const part of Buffer.from(line).toString().split('\\n')) {
        if (!part.startsWith('data: ') || part === 'data: [DONE]') continue
        try { const d = JSON.parse(part.slice(6)).choices?.[0]?.delta?.content; if (d) res.write(`data: {"delta":${JSON.stringify(d)}}\\n\\n`) } catch {}
      }
    }
  } catch(e) { res.write(`data: {"delta":"Error: ${e.message}"}\\n\\n`) }
  res.write('data: [DONE]\\n\\n'); res.end()
})
app.listen(3001)
"""),
        tr("Written: server/index.js"),
        tc("file_write", path="workspace/deliverables/smart-chat/src/App.tsx",
           content="""import { useState, useCallback } from 'react'
interface Message { role: 'user' | 'assistant'; content: string }
export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState(''); const [streaming, setStreaming] = useState(false)
  const send = useCallback(async () => {
    const q = input.trim(); if (!q || streaming) return
    const updated = [...messages, { role: 'user' as const, content: q }]
    setMessages([...updated, { role: 'assistant', content: '' }]); setInput(''); setStreaming(true)
    const res = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ messages: updated }) })
    const reader = res.body!.getReader(); const dec = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      for (const line of dec.decode(value).split('\\n')) {
        if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
        try { const { delta } = JSON.parse(line.slice(6)); if (delta) setMessages(prev => { const n=[...prev]; n[n.length-1]={...n[n.length-1],content:n[n.length-1].content+delta}; return n }) } catch {}
      }
    }
    setStreaming(false)
  }, [input, messages, streaming])
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', background:'#0f172a', fontFamily:'system-ui' }}>
      <div style={{ padding:'12px 20px', background:'#1e293b', borderBottom:'1px solid #334155' }}>
        <span style={{ color:'#f1f5f9', fontWeight:700, fontSize:18 }}>Smart Chat</span>
      </div>
      <div style={{ flex:1, overflow:'auto', padding:'16px 20px' }}>
        {messages.map((m,i) => (
          <div key={i} style={{ marginBottom:10, display:'flex', justifyContent:m.role==='user'?'flex-end':'flex-start' }}>
            <div style={{ maxWidth:'75%', background:m.role==='user'?'#1d4ed8':'#1e293b', color:'#f1f5f9', padding:'10px 14px', borderRadius:10, fontSize:14, lineHeight:1.6, whiteSpace:'pre-wrap' }}>
              {m.content || (streaming && i===messages.length-1?'▌':'')}
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding:'12px 20px', background:'#1e293b', borderTop:'1px solid #334155', display:'flex', gap:10 }}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Message…"
          style={{ flex:1, padding:'10px 14px', borderRadius:8, border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:14, outline:'none' }} />
        <button onClick={send} disabled={!input.trim()||streaming}
          style={{ padding:'10px 18px', borderRadius:8, border:'none', background:'#3b82f6', color:'#fff', cursor:'pointer', fontWeight:600 }}>Send</button>
      </div>
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/smart-chat && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.0s"),
        tc("undertow"),
        tr("Screenshot: clean dark chat UI, user and assistant bubbles, streaming cursor active."),
        # Conversational follow-up
        {"role": "user", "content": "Now add a 'Knowledge Base' panel — the user can paste text into it and that text gets prepended as context for every subsequent message."},
        # Add server-side context injection + frontend panel
        tc("file_edit", path="workspace/deliverables/smart-chat/server/index.js",
           old_text="app.post('/api/chat', async (req, res) => {\n  const { messages } = req.body",
           new_text="app.post('/api/chat', async (req, res) => {\n  const { messages, context } = req.body"),
        tr("Edited: server/index.js — destructure context"),
        tc("file_edit", path="workspace/deliverables/smart-chat/server/index.js",
           old_text="body: JSON.stringify({ model: 'gpt-4o-mini', messages, stream: true })",
           new_text="body: JSON.stringify({ model: 'gpt-4o-mini', stream: true, messages: context ? [{ role: 'system', content: `Context:\\n${context}` }, ...messages] : messages })"),
        tr("Edited: server/index.js — inject context as system message"),
        tc("file_edit", path="workspace/deliverables/smart-chat/src/App.tsx",
           old_text="const [streaming, setStreaming] = useState(false)",
           new_text="const [streaming, setStreaming] = useState(false)\n  const [context, setContext] = useState('')\n  const [showKB, setShowKB] = useState(false)"),
        tr("Edited: src/App.tsx — add context state"),
        tc("file_edit", path="workspace/deliverables/smart-chat/src/App.tsx",
           old_text="body: JSON.stringify({ messages: updated })",
           new_text="body: JSON.stringify({ messages: updated, context: context.trim() || undefined })"),
        tr("Edited: src/App.tsx — pass context to server"),
        tc("file_edit", path="workspace/deliverables/smart-chat/src/App.tsx",
           old_text="<span style={{ color:'#f1f5f9', fontWeight:700, fontSize:18 }}>Smart Chat</span>",
           new_text="<span style={{ color:'#f1f5f9', fontWeight:700, fontSize:18 }}>Smart Chat</span>\n        <button onClick={() => setShowKB(s=>!s)} style={{ marginLeft:'auto', padding:'5px 12px', borderRadius:6, border:'1px solid #334155', background:showKB?'#3b82f6':'#0f172a', color:showKB?'#fff':'#64748b', cursor:'pointer', fontSize:12 }}>📚 Knowledge Base</button>"),
        tr("Edited: src/App.tsx — KB toggle button"),
        tc("file_edit", path="workspace/deliverables/smart-chat/src/App.tsx",
           old_text="<div style={{ flex:1, overflow:'auto', padding:'16px 20px' }}>",
           new_text="{showKB && (<div style={{ background:'#1e293b', borderBottom:'1px solid #334155', padding:'12px 20px' }}><textarea value={context} onChange={e=>setContext(e.target.value)} placeholder=\"Paste knowledge base text here — prepended as context for all messages…\" style={{ width:'100%', height:100, background:'#0f172a', color:'#e2e8f0', border:'1px solid #334155', borderRadius:8, padding:'8px 12px', fontSize:13, resize:'vertical', outline:'none', boxSizing:'border-box' }} /></div>)}\n      <div style={{ flex:1, overflow:'auto', padding:'16px 20px' }}>"),
        tr("Edited: src/App.tsx — KB textarea panel"),
        tc("shell_exec", command="cd workspace/deliverables/smart-chat && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.0s"),
        tc("undertow"),
        tr("Screenshot: chat with 'Knowledge Base' button in header. KB panel expanded showing textarea. Messages use context for relevant answers."),
        tc("message_result", text="Added Knowledge Base panel.\n\nWhen context is pasted, the server prepends it as a system message: `{ role: 'system', content: 'Context:\\n<text>' }`. Toggle with 📚 button. No state lost — existing messages preserved.", done=True),
        tr("Message sent"),
    ]


# ── Main ────────────────────────────────────────────────────────────────────

def build_example(source_fn, messages):
    text = f"<start_of_turn>system\n{AI_SYSTEM}<end_of_turn>\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            text += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role in ("assistant", "tool_call", "tool_result"):
            text += f"<start_of_turn>model\n{content}<end_of_turn>\n"
    return {"text": text, "source": source_fn}


def main():
    v1_examples = []
    if V1.exists():
        with open(V1) as f:
            v1_examples = [json.loads(l) for l in f if l.strip()]
        print(f"Loaded {len(v1_examples)} from v1")

    new_examples = [
        ("rag01_doc_qa",           rag01_doc_qa()),
        ("rag02_model_selector",   rag02_model_selector()),
        ("rag03_error_recovery",   rag03_error_recovery()),
        ("rag04_conversational",   rag04_conversational()),
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for ex in v1_examples:
            f.write(json.dumps(ex) + "\n")
        for source, msgs in new_examples:
            obj = build_example(source, msgs)
            f.write(json.dumps(obj) + "\n")
            print(f"  {source}: {len(msgs)} msgs -> {len(obj['text'])} chars")

    total = len(v1_examples) + len(new_examples)
    print(f"\nTotal: {total} ({len(v1_examples)} v1 + {len(new_examples)} new)")
    print(f"Wrote to {OUT}")


if __name__ == "__main__":
    main()
