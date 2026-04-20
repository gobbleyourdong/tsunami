/**
 * Fullstack composition fixture: shared/types.ts pattern, useApi CRUD
 * hook usage, optimistic UI, error/loading states. Mirrors what a
 * drone naturally writes when wiring a CRUD list against the Express
 * server in `server/index.js`.
 *
 * NOT a test file — picked up by tsc via tsconfig include `__fixtures__`.
 * Locks the contract so widening the UI or hook surface can't silently
 * break drone-side patterns.
 */
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  Input,
  Skeleton,
  Switch,
  Text,
} from "../src/components/ui"
import { useApi } from "../src/components/useApi"
import { useState } from "react"

// Shared type — drones write this in `shared/types.ts` and import it
// from BOTH `src/` and `server/`. The fixture imports it locally to
// stand in for the shared module that user code creates.
interface Item {
  id?: number
  name: string
  description?: string
  status?: "active" | "archived"
  data?: Record<string, unknown>
}

function ItemRow({ item, onArchive, onDelete }: {
  item: Item
  onArchive: () => void
  onDelete: () => void
}) {
  return (
    <Card variant="filled" padding="md" hoverable>
      <Flex justify="between" align="center" gap={3}>
        <div>
          <Heading level={3} size="lg">{item.name}</Heading>
          {item.description && <Text muted size="sm">{item.description}</Text>}
        </div>
        <Flex gap={2} align="center">
          <Badge variant={item.status === "active" ? "success" : "secondary"} pill>
            {item.status ?? "active"}
          </Badge>
          <Button variant="outline" size="sm" onClick={onArchive}>Archive</Button>
          <Button variant="destructive" size="sm" onClick={onDelete}>Delete</Button>
        </Flex>
      </Flex>
    </Card>
  )
}

function CreateForm({ onSubmit }: { onSubmit: (item: Item) => Promise<void> }) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [busy, setBusy] = useState(false)
  return (
    <Card padding="lg">
      <Heading level={2} size="2xl">New item</Heading>
      <Flex direction="col" gap={3}>
        <Input
          label="Name"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Item name"
          fullWidth
        />
        <Input
          label="Description"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Optional notes"
          fullWidth
        />
        <Flex justify="end">
          <Button
            variant="primary"
            disabled={!name || busy}
            loading={busy}
            onClick={async () => {
              setBusy(true)
              await onSubmit({ name, description, status: "active" })
              setName("")
              setDescription("")
              setBusy(false)
            }}
          >
            Create
          </Button>
        </Flex>
      </Flex>
    </Card>
  )
}

export default function FullstackFixture() {
  // useApi exposes { data, loading, error, create, update, remove, refresh }.
  const { data, loading, error, create, update, remove } = useApi<Item>("items")
  const [confirmId, setConfirmId] = useState<number | null>(null)

  return (
    <Flex direction="col" gap={4}>
      <Heading level={1} size="3xl">Items</Heading>

      <CreateForm onSubmit={async item => { await create(item) }} />

      {error && <Alert variant="destructive" title="Failed to load">{error}</Alert>}

      {loading && (
        <Flex direction="col" gap={2}>
          <Skeleton variant="rect" width="100%" height={64} />
          <Skeleton variant="rect" width="100%" height={64} />
          <Skeleton variant="rect" width="100%" height={64} />
        </Flex>
      )}

      {!loading && data.length === 0 && (
        <Alert type="info" title="No items yet">Create your first item above.</Alert>
      )}

      {!loading && data.map(item => (
        <ItemRow
          key={item.id}
          item={item}
          onArchive={() => item.id != null && update(item.id, { status: "archived" })}
          onDelete={() => item.id != null && setConfirmId(item.id)}
        />
      ))}

      <Dialog
        open={confirmId !== null}
        onOpenChange={(open) => !open && setConfirmId(null)}
        title="Delete item?"
        description="This cannot be undone."
        size="sm"
        footer={
          <Flex gap={2}>
            <Button variant="outline" onClick={() => setConfirmId(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (confirmId !== null) await remove(confirmId)
                setConfirmId(null)
              }}
            >
              Delete
            </Button>
          </Flex>
        }
      >
        <Switch defaultChecked label="I understand this is permanent" />
      </Dialog>
    </Flex>
  )
}
