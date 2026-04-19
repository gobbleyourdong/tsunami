/**
 * Drone-natural prop-shape fixture for react-app scaffold.
 *
 * Each block exercises a prop combo a Qwen3.6 drone naturally emits — names
 * cribbed from shadcn / radix / chakra / mantine conventions. If tsc is clean
 * here, the scaffold is meeting the drone where it is.
 *
 * NOT a test file (no .test/.spec suffix) — vitest skips it. Picked up by
 * tsc via the tsconfig `include` covering `__fixtures__`. Not in vite's
 * import graph so it won't bundle.
 *
 * Iteration rule from GAP.md: when a prop fails, widen the COMPONENT, not
 * the fixture. The fixture freezes drone vocabulary as a regression net.
 */
import {
  Accordion,
  Alert,
  AnimatedCounter,
  AnnouncementBar,
  Avatar,
  Badge,
  BeforeAfter,
  Box,
  Button,
  Calendar,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Chart,
  ColorPicker,
  Dialog,
  Dropdown,
  Flex,
  GlowCard,
  GradientText,
  Heading,
  Image,
  Input,
  Marquee,
  MetricCard,
  NotificationCenter,
  Parallax,
  Progress,
  RichTextEditor,
  ScrollArea,
  ScrollReveal,
  Select,
  Skeleton,
  Slideshow,
  StarRating,
  StatGrid,
  Switch,
  Text,
  Timeline,
  Tooltip,
  TypeWriter,
} from "@/components/ui"
import { useState } from "react"

export default function DroneNaturalFixture() {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<Date | undefined>(undefined)
  const [color, setColor] = useState("#4a9eff")
  const [option, setOption] = useState("a")
  const [rating, setRating] = useState(3)
  const [editor, setEditor] = useState("")

  return (
    <div>
      {/* === Layout primitives === */}
      <Box padding={4} bg="bg-1" bordered>
        <Flex direction="column" spacing={4} inline>
          <Flex direction="row" gap={4} align="center" justify="between">
            <Heading level={1} size="5xl" weight="bold" color="primary">Title</Heading>
            <Heading level={2} size="4xl" as="h2">Subtitle</Heading>
          </Flex>
        </Flex>
      </Box>

      {/* === Text and gradients === */}
      <Text size="xs" muted>tiny muted</Text>
      <Text size="4xl" weight="semibold" color="muted">big</Text>
      <GradientText as="h1" size="6xl" from="#f06" to="#0cf" animate>
        Headline
      </GradientText>

      {/* === Buttons === */}
      <Button variant="primary" size="md">Primary</Button>
      <Button variant="solid" size="xs">Solid extra small</Button>
      <Button variant="subtle" size="xl" loading disabled fullWidth>
        Subtle full width loading
      </Button>
      <Button variant="outline" size="md" leftIcon={<span>←</span>} rightIcon={<span>→</span>}>
        With icons
      </Button>

      {/* === Cards === */}
      <Card variant="elevated" padding="lg" hoverable interactive>
        <CardHeader>
          <CardTitle>Title</CardTitle>
        </CardHeader>
        <CardContent>Body</CardContent>
      </Card>
      <GlowCard glowColor="#4a9eff" intensity={0.8} padding="md">
        Glow body
      </GlowCard>

      {/* === Badges === */}
      <Badge variant="success" size="sm" color="green">OK</Badge>
      <Badge variant="destructive" pill outline>Bad</Badge>
      <Badge dot status="online">User</Badge>

      {/* === Avatars === */}
      <Avatar fallback="JB" shape="square" size="lg" status="online" />
      <Avatar src="/avatar.jpg" alt="user" size={48} radius="full" />

      {/* === Inputs === */}
      <Input
        label="Email"
        placeholder="you@example.com"
        value=""
        onChange={() => {}}
        error="Required"
        helperText="We never share your email"
        leftIcon={<span>@</span>}
        size="md"
      />
      <Input prefix="$" suffix=".00" type="number" />

      {/* === Selects === */}
      <Select
        value={option}
        onValueChange={setOption}
        options={[
          { value: "a", label: "Apple" },
          { value: "b", label: "Banana" },
        ]}
        placeholder="Pick one"
        label="Fruit"
        disabled
        error="Choose one"
      />

      {/* === Switches === */}
      <Switch checked size="lg" disabled color="success" label="Enable" />
      <Switch value={false} onValueChange={() => {}} size="md" />

      {/* === Progress === */}
      <Progress value={42} max={100} size="lg" color="success" showValue />
      <Progress value={75} variant="striped" indeterminate />

      {/* === Skeleton === */}
      <Skeleton variant="text" lines={3} animation="pulse" />
      <Skeleton variant="rect" width={200} height={120} animation="wave" />
      <Skeleton variant="circle" size={40} />

      {/* === Tooltip === */}
      <Tooltip content="hello" placement="top" delay={300}>
        <Button>Hover me</Button>
      </Tooltip>
      <Tooltip text="legacy" position="bottom">
        <span>x</span>
      </Tooltip>

      {/* === Dialog === */}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Confirm"
        description="Are you sure?"
        size="md"
        footer={<Button onClick={() => setOpen(false)}>OK</Button>}
      >
        Body
      </Dialog>

      {/* === Alert === */}
      <Alert variant="success" title="Saved" icon={<span>✓</span>} dismissible onDismiss={() => {}}>
        All good
      </Alert>
      <Alert type="error" title="Oops">Boom</Alert>

      {/* === Accordion === */}
      <Accordion
        type="single"
        defaultOpen={0}
        collapsible
        items={[
          { title: "Q1", content: "A1" },
          { title: "Q2", content: "A2" },
        ]}
      />

      {/* === Marquee + TypeWriter === */}
      <Marquee speed={20} duration={20} gap={20} pauseOnHover>
        <span>scrolling</span>
      </Marquee>
      <TypeWriter words={["hello", "world"]} loop speed={60} cursor />

      {/* === Slideshow === */}
      <Slideshow
        images={["/a.jpg", "/b.jpg"]}
        autoplay
        duration={5000}
        height={300}
        showDots
        showArrows
      />

      {/* === Animated counter === */}
      <AnimatedCounter from={0} to={1000} duration={1500} format="number" />
      <AnimatedCounter value={42} prefix="$" suffix="k" precision={1} />

      {/* === MetricCard / StatGrid === */}
      <MetricCard
        title="Revenue"
        label="Revenue"
        value={1234}
        change={12}
        delta={12}
        trend="up"
        prefix="$"
      />
      <StatGrid
        cols={3}
        columns={3}
        items={[
          { label: "Users", value: 1200, delta: 5 },
          { label: "Sales", value: 84, delta: -3 },
        ]}
        gap={16}
      />

      {/* === Chart === */}
      <Chart
        kind="line"
        type="line"
        series={[{ x: 1, y: 10 }]}
        data={[{ x: 1, y: 10 }]}
        height={240}
        title="Sales"
        legend
        animated
      />

      {/* === Calendar === */}
      <Calendar
        selected={selected}
        value={selected}
        onSelect={setSelected}
        onChange={setSelected}
        mode="single"
      />

      {/* === Star rating === */}
      <StarRating value={rating} onValueChange={setRating} count={5} readOnly={false} />

      {/* === Image === */}
      <Image src="/hero.jpg" alt="hero" width={400} height={200} radius={8} fit="cover" />

      {/* === Color picker === */}
      <ColorPicker value={color} onChange={setColor} swatches={["#f06","#0cf"]} label="Color" />

      {/* === BeforeAfter === */}
      <BeforeAfter
        before="/a.jpg"
        after="/b.jpg"
        beforeImage="/a.jpg"
        afterImage="/b.jpg"
        labelBefore="Before"
        labelAfter="After"
        height={300}
      />

      {/* === Announcement bar === */}
      <AnnouncementBar message="Sale!" text="Sale!" link={{ text: "Shop", href: "#" }} />

      {/* === Notification center === */}
      <NotificationCenter
        toasts={[]}
        notifications={[]}
        onDismiss={() => {}}
        position="top-right"
      />

      {/* === Dropdown === */}
      <Dropdown
        trigger={<Button>Menu</Button>}
        options={[{ label: "One", onClick: () => {} }]}
        items={[{ label: "One", onClick: () => {} }]}
      />

      {/* === Parallax + ScrollReveal === */}
      <Parallax speed={0.5} offset={50}>
        <div>parallax</div>
      </Parallax>
      <ScrollReveal animation="slide-up" direction="up" delay={100} duration={500}>
        <div>reveal</div>
      </ScrollReveal>

      {/* === ScrollArea === */}
      <ScrollArea height={400} maxHeight={400} orientation="vertical">
        <div>scrollable</div>
      </ScrollArea>

      {/* === Rich text === */}
      <RichTextEditor
        value={editor}
        defaultValue=""
        onChange={setEditor}
        placeholder="Write..."
        minHeight={150}
      />

      {/* === Timeline === */}
      <Timeline
        items={[
          { year: 2024, event: "founded", body: "..." },
          { date: "Jan 1", title: "launch", description: "..." },
          { label: "Q3", body: "..." },
        ]}
      />
    </div>
  )
}
