/**
 * Dashboard composition fixture: sidebar nav, KPI tiles, status cards,
 * activity feed, dropdown menus, command palette. The dashboard scaffold
 * doesn't ship Chart/MetricCard out of the box — drones bring recharts
 * directly into their App.tsx and compose primitives from ./components/ui.
 */
import {
  Accordion,
  Alert,
  AnimatedCounter,
  Avatar,
  Badge,
  Button,
  Card,
  CommandPalette,
  Dialog,
  Dropdown,
  Flex,
  Heading,
  Input,
  Progress,
  Skeleton,
  Switch,
  Text,
  Timeline,
  Tooltip,
} from "../src/components/ui"
import Box from "../src/components/ui/Box"
import { useState } from "react"

function Sidebar() {
  return (
    <Box bg="bg-1" padding={4} bordered>
      <Flex direction="col" gap={2} align="stretch">
        <Heading level={1} size="lg">Console</Heading>
        {["Overview", "Customers", "Billing", "Logs", "Settings"].map(item => (
          <Button key={item} variant="ghost" size="sm" fullWidth>{item}</Button>
        ))}
      </Flex>
    </Box>
  )
}

function TopBar() {
  return (
    <Flex justify="between" align="center" gap={4}>
      <Input placeholder="Search anything..." leftIcon={<span>🔍</span>} size="sm" />
      <Flex gap={3} align="center">
        <Tooltip content="Notifications" placement="bottom">
          <Button variant="ghost" size="icon" aria-label="notifications">🔔</Button>
        </Tooltip>
        <Dropdown
          trigger={<Avatar fallback="JB" size="sm" status="online" />}
          options={[
            { label: "Profile", onClick: () => {} },
            { label: "Sign out", onClick: () => {}, danger: true },
          ]}
        />
      </Flex>
    </Flex>
  )
}

function KPI({ label, value, delta, suffix }: { label: string; value: number; delta?: number; suffix?: string }) {
  const positive = (delta ?? 0) >= 0
  return (
    <Card variant="filled" padding="md" hoverable>
      <Text size="xs" color="muted" weight="semibold">{label}</Text>
      <Heading level={2} size="3xl">
        <AnimatedCounter value={value} suffix={suffix} />
      </Heading>
      {delta != null && (
        <Badge variant={positive ? "success" : "destructive"} size="sm" pill>
          {positive ? "↑" : "↓"} {Math.abs(delta)}%
        </Badge>
      )}
    </Card>
  )
}

function KPIGrid() {
  return (
    <Flex gap={4} wrap>
      <KPI label="MRR"       value={48230} delta={12.4} suffix="$" />
      <KPI label="Customers" value={1284}  delta={3.2} />
      <KPI label="Churn"     value={1.8}   delta={-0.4} suffix="%" />
      <KPI label="NPS"       value={62} />
    </Flex>
  )
}

function StatusList() {
  return (
    <Card variant="default" padding="md">
      <Heading level={3} size="lg">System status</Heading>
      <Flex direction="col" gap={3}>
        {[
          { label: "API",    pct: 99.97, color: "success" },
          { label: "Worker", pct: 92.30, color: "warning" },
          { label: "DB",     pct: 100,   color: "success" },
        ].map(row => (
          <Flex key={row.label} align="center" gap={3}>
            <Text size="sm" weight="semibold">{row.label}</Text>
            <Progress value={row.pct} size="sm" color={row.color} showValue />
          </Flex>
        ))}
      </Flex>
    </Card>
  )
}

function Activity() {
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Recent activity</Heading>
      <Timeline items={[
        { year: 2026, event: "Spend cap raised", body: "Pro tier autoscale enabled." },
        { date: "9:14 AM", title: "Deploy", description: "main → prod (#a31bf0e)" },
        { label: "Earlier", body: "3 customers signed up overnight." },
      ]} />
    </Card>
  )
}

function SettingsPanel() {
  const [a, setA] = useState(true)
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Notifications</Heading>
      <Flex direction="col" gap={3}>
        <Switch checked={a} onCheckedChange={setA} label="Email alerts" size="md" color="primary" />
        <Switch defaultChecked label="Push" size="md" color="success" />
        <Switch label="Daily digest" size="sm" disabled />
      </Flex>
      <Accordion type="single" collapsible items={[
        { title: "Advanced", content: "Per-channel toggles." },
      ]} />
    </Card>
  )
}

function LoadingState() {
  return (
    <Card padding="md">
      <Skeleton variant="text" lines={2} />
      <Skeleton variant="rect" width="100%" height={120} />
    </Card>
  )
}

function ConfirmDialog() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="destructive" onClick={() => setOpen(true)}>Delete account</Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Delete account?"
        description="This cannot be undone."
        size="sm"
        footer={
          <Flex gap={2}>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="destructive">Delete</Button>
          </Flex>
        }
      >
        Are you sure?
      </Dialog>
    </>
  )
}

function CmdK() {
  return (
    <CommandPalette
      placeholder="Type a command…"
      trigger="k"
      commands={[
        { id: "g-h", label: "Go to Home", action: () => {}, shortcut: "g h" },
        { id: "g-s", label: "Go to Settings", action: () => {}, shortcut: "g s", category: "Navigation" },
        { id: "logout", label: "Sign out", action: () => {}, category: "Account" },
      ]}
    />
  )
}

function Banner() {
  return (
    <Alert variant="warning" title="Quota at 90%" dismissible onDismiss={() => {}}>
      Upgrade or trim usage before midnight to avoid throttling.
    </Alert>
  )
}

export default function DashboardFixture() {
  return (
    <Flex gap={4}>
      <Sidebar />
      <Flex direction="col" gap={4}>
        <TopBar />
        <Banner />
        <KPIGrid />
        <Flex gap={4}>
          <StatusList />
          <Activity />
          <SettingsPanel />
        </Flex>
        <LoadingState />
        <ConfirmDialog />
        <CmdK />
      </Flex>
    </Flex>
  )
}
