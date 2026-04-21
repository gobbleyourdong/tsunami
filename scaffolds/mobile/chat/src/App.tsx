import { MessageList, Composer, OfflineBanner } from "./components"

export default function App() {
  return (
    <div className="chat">
      <header className="chat-header">
        <h1>Chat</h1>
        <div className="status">PWA scaffold — local echo</div>
      </header>
      <OfflineBanner />
      <MessageList />
      <Composer />
    </div>
  )
}
