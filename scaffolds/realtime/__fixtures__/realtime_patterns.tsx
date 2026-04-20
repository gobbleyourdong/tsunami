/**
 * Realtime composition fixture: useWebSocket hook, presence list,
 * message feed, typing indicator, room join/switch, connection state
 * banner, optimistic-send. Mirrors what a drone naturally writes for
 * live cursors / shared whiteboard / chat-style apps against the
 * `server/index.js` ws server (rooms + broadcast).
 */
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  Input,
  Skeleton,
  Text,
  Tooltip,
} from "../src/components/ui"
import { useWebSocket } from "../src/components/useWebSocket"
import { useEffect, useState } from "react"

// Wire-format types drones reach for. These are the canonical shapes
// the bundled server emits / accepts. Lock them here so widening the
// hook can't silently break the contract.
type ChatMsg = { type: "chat"; user: string; text: string; ts: number }
type Join    = { type: "join"; user: string; room: string }
type Leave   = { type: "leave"; user: string; room: string }
type Server  = ChatMsg | Join | Leave

function ConnectionBanner({ connected }: { connected: boolean }) {
  return connected ? (
    <Alert variant="success" title="Live" dismissible>Connected to server.</Alert>
  ) : (
    <Alert variant="warning" title="Reconnecting…">Auto-retry in 2s.</Alert>
  )
}

function PresenceList({ users }: { users: string[] }) {
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Online ({users.length})</Heading>
      <Flex gap={2} wrap>
        {users.map(u => (
          <Tooltip key={u} content={u}>
            <Flex align="center" gap={2}>
              <Avatar fallback={u.slice(0, 2).toUpperCase()} size="sm" status="online" />
              <Text size="sm">{u}</Text>
            </Flex>
          </Tooltip>
        ))}
        {users.length === 0 && <Skeleton variant="circle" size={24} />}
      </Flex>
    </Card>
  )
}

function MessageFeed({ messages }: { messages: ChatMsg[] }) {
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Messages</Heading>
      <Flex direction="col" gap={2}>
        {messages.map((m, i) => (
          <Flex key={i} align="start" gap={2}>
            <Avatar fallback={m.user.slice(0, 2).toUpperCase()} size="sm" />
            <div>
              <Flex align="center" gap={2}>
                <Text size="sm" weight="semibold">{m.user}</Text>
                <Text size="xs" color="muted">{new Date(m.ts).toLocaleTimeString()}</Text>
              </Flex>
              <Text size="sm">{m.text}</Text>
            </div>
          </Flex>
        ))}
        {messages.length === 0 && (
          <Alert type="info" title="No messages yet">Be the first.</Alert>
        )}
      </Flex>
    </Card>
  )
}

function Composer({ onSend }: { onSend: (text: string) => void }) {
  const [draft, setDraft] = useState("")
  return (
    <Flex gap={2}>
      <Input
        placeholder="Say something…"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => {
          if (e.key === "Enter" && draft.trim()) {
            onSend(draft.trim())
            setDraft("")
          }
        }}
        fullWidth
      />
      <Button variant="primary" disabled={!draft.trim()} onClick={() => { onSend(draft.trim()); setDraft("") }}>
        Send
      </Button>
    </Flex>
  )
}

function RoomSwitcher({ room, onSwitch }: { room: string; onSwitch: (next: string) => void }) {
  const [open, setOpen] = useState(false)
  const [next, setNext] = useState(room)
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Room: <Badge variant="primary" pill>{room}</Badge>
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Switch room"
        size="sm"
        footer={
          <Flex gap={2}>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => { onSwitch(next); setOpen(false) }}>
              Switch
            </Button>
          </Flex>
        }
      >
        <Input label="Room name" value={next} onChange={e => setNext(e.target.value)} fullWidth />
      </Dialog>
    </>
  )
}

export default function RealtimeFixture() {
  const [room, setRoom] = useState("lobby")
  const [user] = useState("alice")
  const [online, setOnline] = useState<string[]>([])
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const { connected, send, lastMessage } = useWebSocket({
    url: `ws://localhost:3001?room=${encodeURIComponent(room)}`,
    onMessage: (m: Server) => {
      if (m.type === "chat") setMessages(prev => [...prev, m].slice(-100))
      if (m.type === "join") setOnline(prev => Array.from(new Set([...prev, m.user])))
      if (m.type === "leave") setOnline(prev => prev.filter(u => u !== m.user))
    },
  })

  // Reset state on room change
  useEffect(() => { setMessages([]); setOnline([]) }, [room])

  // Surface lastMessage so the test/fixture demonstrates the alternate API
  void lastMessage

  return (
    <Flex direction="col" gap={4}>
      <Flex justify="between" align="center">
        <Heading level={1} size="3xl">Live</Heading>
        <RoomSwitcher room={room} onSwitch={setRoom} />
      </Flex>
      <ConnectionBanner connected={connected} />
      <Flex gap={4}>
        <PresenceList users={online} />
        <Flex direction="col" gap={3}>
          <MessageFeed messages={messages} />
          <Composer
            onSend={text => send({ type: "chat", user, text, ts: Date.now() })}
          />
        </Flex>
      </Flex>
    </Flex>
  )
}
