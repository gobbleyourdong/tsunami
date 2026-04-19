/**
 * Second drone-natural fixture covering composition patterns common to
 * landing / pricing / dashboard / gallery scaffolds. Same rule as the first
 * fixture: when something fails to compile, widen the COMPONENT.
 */
import {
  Alert,
  AnimatedCounter,
  Avatar,
  Badge,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
  Chart,
  Flex,
  GradientText,
  Heading,
  IconButton,
  Image,
  MetricCard,
  Progress,
  StatGrid,
  Skeleton,
  Tooltip,
  Text,
} from "@/components/ui"
import Box from "@/components/ui/Box"

function Hero() {
  return (
    <Box padding={8} bg="bg-1" rounded shadow>
      <Flex direction="column" align="center" gap={4}>
        <GradientText as="h1" size="6xl" from="#f06" via="#a0f" to="#0cf">
          Build faster
        </GradientText>
        <Text size="xl" color="muted">A modern toolkit for the rest of us.</Text>
        <Flex gap={3}>
          <Button variant="primary" size="lg">Start free</Button>
          <Button variant="outline" size="lg" leftIcon={<span>▶</span>}>
            Watch demo
          </Button>
        </Flex>
      </Flex>
    </Box>
  )
}

function PricingCard({ tier, price, popular }: { tier: string; price: string; popular?: boolean }) {
  return (
    <Card variant={popular ? "elevated" : "outline"} padding="lg" hoverable>
      <CardHeader>
        <Flex justify="between" align="center">
          <CardTitle>{tier}</CardTitle>
          {popular && <Badge variant="primary" pill>Popular</Badge>}
        </Flex>
        <CardDescription>For teams that ship.</CardDescription>
      </CardHeader>
      <CardContent>
        <Heading level={2} size="4xl" weight="extrabold">{price}</Heading>
        <Text size="sm" muted>per seat / month</Text>
      </CardContent>
      <CardFooter>
        <Button fullWidth variant={popular ? "primary" : "outline"}>
          Choose {tier}
        </Button>
      </CardFooter>
    </Card>
  )
}

function DashboardKPIs() {
  return (
    <StatGrid cols={4} gap={16} items={[
      { label: "MRR",       value: <AnimatedCounter value={48230} prefix="$" />, delta: 12.4 },
      { label: "Customers", value: <AnimatedCounter value={1284} />,             delta: 3.2 },
      { label: "Churn",     value: <AnimatedCounter value={1.8} precision={1} suffix="%" />, delta: -0.4, invertDelta: true },
      { label: "NPS",       value: <AnimatedCounter value={62} />,                trend: "up" },
    ]} />
  )
}

function ChartsRow() {
  const data = [
    { x: "Jan", y: 30 }, { x: "Feb", y: 42 }, { x: "Mar", y: 55 },
    { x: "Apr", y: 48 }, { x: "May", y: 70 }, { x: "Jun", y: 88 },
  ]
  return (
    <Flex gap={4}>
      <Card padding="md">
        <CardTitle>Revenue (line)</CardTitle>
        <Chart kind="line" series={data} height={220} legend />
      </Card>
      <Card padding="md">
        <CardTitle>Signups (bar)</CardTitle>
        <Chart type="bar" data={data} height={220} grid={false} />
      </Card>
      <Card padding="md">
        <CardTitle>Mix</CardTitle>
        <Chart kind="pie" series={data} height={220} showLegend />
      </Card>
    </Flex>
  )
}

function GalleryGrid() {
  const imgs = ["/g1.jpg", "/g2.jpg", "/g3.jpg", "/g4.jpg"]
  return (
    <Box>
      <Heading level={2} size="3xl">Recent work</Heading>
      <Flex wrap gap={3}>
        {imgs.map((src, i) => (
          <Image key={i} src={src} alt={`piece ${i}`} width={240} height={160} radius={12} fit="cover" />
        ))}
      </Flex>
    </Box>
  )
}

function ToastBar() {
  return (
    <Flex direction="col" gap={2}>
      <Alert variant="success" title="Saved" dismissible onDismiss={() => {}}>Your changes are live.</Alert>
      <Alert type="warning" title="Heads up" icon={<span>!</span>}>Quota at 90%.</Alert>
      <Alert variant="destructive" title="Failed" dismissable onDismiss={() => {}}>Could not save.</Alert>
    </Flex>
  )
}

function PeopleStrip() {
  return (
    <Flex gap={2} align="center">
      <Avatar fallback="JB" size="lg" status="online" />
      <Avatar fallback="MK" size="lg" status="busy" />
      <Avatar src="/u.jpg" alt="user" size={48} radius="full" />
      <IconButton variant="ghost" size="icon" aria-label="add">+</IconButton>
    </Flex>
  )
}

function LoadingState() {
  return (
    <Flex direction="col" gap={3}>
      <Skeleton variant="text" lines={3} />
      <Skeleton variant="rect" width="100%" height={200} />
      <Skeleton variant="circle" size={64} />
    </Flex>
  )
}

function ProgressRow() {
  return (
    <Flex direction="col" gap={3}>
      <Progress value={25} size="sm" color="primary" showValue />
      <Progress value={62} size="md" color="success" />
      <Progress value={88} size="lg" variant="striped" />
      <Progress indeterminate size="md" />
    </Flex>
  )
}

function MetricsRow() {
  return (
    <Flex gap={3}>
      <MetricCard title="Latency" value="42ms" delta={-5} invertDelta hint="p95" />
      <MetricCard label="Errors" value={3} change={-2} trend="down" suffix="/min" />
      <MetricCard title="Uptime" value="99.97%" trend="flat" />
    </Flex>
  )
}

function TooltipRow() {
  return (
    <Flex gap={2}>
      <Tooltip content="Hi" placement="top" delay={150}><Button>Top</Button></Tooltip>
      <Tooltip text="Hi" position="bottom"><Button>Bottom</Button></Tooltip>
    </Flex>
  )
}

export default function LandingDashboardGalleryFixture() {
  return (
    <Box>
      <Hero />
      <Flex gap={4}>
        <PricingCard tier="Starter" price="$0" />
        <PricingCard tier="Pro" price="$29" popular />
        <PricingCard tier="Team" price="$99" />
      </Flex>
      <DashboardKPIs />
      <ChartsRow />
      <GalleryGrid />
      <ToastBar />
      <PeopleStrip />
      <LoadingState />
      <ProgressRow />
      <MetricsRow />
      <TooltipRow />
    </Box>
  )
}
