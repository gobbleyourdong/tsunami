# AI App Scaffold

React + Express SSE streaming chatbot scaffold.

## Architecture

```
src/hooks/useChat.ts    — streaming SSE hook (messages, sendMessage, isStreaming)
server/index.js         — Express proxy that hides your API key + streams LLM tokens
```

## Quick start

1. Copy `.env.example` → `.env`, add your `OPENAI_API_KEY`
2. `npm run dev` — starts React (Vite :5173) + Express proxy (:3001)
3. Replace `src/App.tsx` with your chat UI

## useChat API

```tsx
const { messages, sendMessage, isStreaming, error, clearMessages } = useChat(systemPrompt?)

// messages: { role: 'user' | 'assistant', content: string }[]
// sendMessage(text): sends user message, streams assistant reply token-by-token
// isStreaming: true while tokens are arriving
// clearMessages(): resets conversation
```

## Customizing the LLM provider

Edit `server/index.js` — the fetch URL and auth headers.
Works with any OpenAI-compatible API: OpenAI, Together.ai, Groq, Ollama, etc.
