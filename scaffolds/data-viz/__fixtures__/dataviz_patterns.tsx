/**
 * Data-viz composition fixture: stat rows, filter panel, color legend,
 * data tile grids, "no data" empty states. The data-viz scaffold leaves
 * recharts to user code; the fixture exercises ONLY shipped UI primitives
 * the way a drone naturally drives them in viz contexts.
 */
import {
  Alert,
  AnimatedCounter,
  Badge,
  Box,
  Button,
  Card,
  ColorPicker,
  Dropdown,
  Flex,
  Heading,
  Input,
  Progress,
  Select,
  Skeleton,
  Switch,
  Text,
  Tooltip,
} from "../src/components/ui"
import { useState } from "react"

function FilterBar() {
  const [period, setPeriod] = useState("7d")
  const [granularity, setGranularity] = useState("day")
  return (
    <Card variant="filled" padding="md">
      <Flex gap={3} wrap align="end">
        <Select
          label="Period"
          value={period}
          onValueChange={setPeriod}
          options={[
            { value: "1d",  label: "Last 24 hours" },
            { value: "7d",  label: "Last 7 days" },
            { value: "30d", label: "Last 30 days" },
            { value: "ytd", label: "Year to date" },
          ]}
          size="sm"
        />
        <Select
          label="Granularity"
          value={granularity}
          onValueChange={setGranularity}
          options={[
            { value: "hour", label: "Hour" },
            { value: "day",  label: "Day" },
            { value: "week", label: "Week" },
          ]}
          size="sm"
        />
        <Input label="Search series" placeholder="cpu, mem, …" size="sm" leftIcon={<span>🔍</span>} />
        <Button variant="primary" size="sm">Apply</Button>
        <Button variant="outline" size="sm">Reset</Button>
      </Flex>
    </Card>
  )
}

function StatTile({ label, value, delta, suffix }: { label: string; value: number; delta?: number; suffix?: string }) {
  const positive = (delta ?? 0) >= 0
  return (
    <Card padding="md" hoverable>
      <Text size="xs" color="muted" weight="semibold">{label}</Text>
      <Heading level={2} size="3xl">
        <AnimatedCounter value={value} suffix={suffix} format="compact" />
      </Heading>
      {delta != null && (
        <Badge variant={positive ? "success" : "destructive"} size="sm" pill>
          {positive ? "↑" : "↓"} {Math.abs(delta)}%
        </Badge>
      )}
    </Card>
  )
}

function StatRow() {
  return (
    <Flex gap={3} wrap>
      <StatTile label="Pageviews" value={1240000} delta={3.4} />
      <StatTile label="Sessions"  value={48230}   delta={1.1} />
      <StatTile label="Bounce"    value={32.7}    delta={-0.6} suffix="%" />
      <StatTile label="Avg time"  value={184}     delta={2.3} suffix="s" />
    </Flex>
  )
}

function ChartPlaceholder({ title, height }: { title: string; height: number }) {
  return (
    <Card padding="md">
      <Flex justify="between" align="center">
        <Heading level={3} size="lg">{title}</Heading>
        <Dropdown
          trigger={<Button variant="ghost" size="sm">⋯</Button>}
          options={[
            { label: "Export PNG", onClick: () => {} },
            { label: "Export CSV", onClick: () => {} },
          ]}
        />
      </Flex>
      <Box bg="bg-2" rounded style={{ height }}>
        <Skeleton variant="rect" width="100%" height={height} animation="wave" />
      </Box>
    </Card>
  )
}

function ChartGrid() {
  return (
    <Flex gap={3} wrap>
      <ChartPlaceholder title="Traffic" height={240} />
      <ChartPlaceholder title="Conversions" height={240} />
      <ChartPlaceholder title="Latency p95" height={240} />
      <ChartPlaceholder title="Errors / min" height={240} />
    </Flex>
  )
}

function Legend() {
  const [a, setA] = useState("#4a9eff")
  const [b, setB] = useState("#34d4b0")
  const [c, setC] = useState("#f0b040")
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Series colors</Heading>
      <Flex gap={3} wrap>
        <Flex gap={2} align="center"><ColorPicker value={a} onChange={setA} swatches={["#4a9eff","#a070f0"]} /><Text size="sm">cpu</Text></Flex>
        <Flex gap={2} align="center"><ColorPicker value={b} onChange={setB} /><Text size="sm">mem</Text></Flex>
        <Flex gap={2} align="center"><ColorPicker value={c} onChange={setC} /><Text size="sm">disk</Text></Flex>
      </Flex>
    </Card>
  )
}

function ToggleRow() {
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Display</Heading>
      <Flex direction="col" gap={2}>
        <Switch defaultChecked label="Show grid" />
        <Switch defaultChecked label="Show tooltip" />
        <Switch label="Log scale" size="sm" />
      </Flex>
    </Card>
  )
}

function NoData() {
  return (
    <Alert type="info" title="No data" dismissible>
      Try widening the date range or removing a filter.
    </Alert>
  )
}

function ProgressGrid() {
  return (
    <Card padding="md">
      <Heading level={3} size="lg">Quota usage</Heading>
      <Flex direction="col" gap={3}>
        {[{ k: "API calls",  v: 62 }, { k: "Storage", v: 38 }, { k: "Compute", v: 91 }].map(r => (
          <Flex key={r.k} align="center" gap={3}>
            <Tooltip content={`${r.k}: ${r.v}%`}>
              <Text size="sm" weight="semibold">{r.k}</Text>
            </Tooltip>
            <Progress value={r.v} size="md" color={r.v > 80 ? "danger" : "primary"} showValue />
          </Flex>
        ))}
      </Flex>
    </Card>
  )
}

export default function DataVizFixture() {
  return (
    <Flex direction="col" gap={4}>
      <FilterBar />
      <StatRow />
      <ChartGrid />
      <Flex gap={3}>
        <Legend />
        <ToggleRow />
        <ProgressGrid />
      </Flex>
      <NoData />
    </Flex>
  )
}
