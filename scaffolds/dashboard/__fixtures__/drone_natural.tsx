/**
 * Shared drone-natural prop-shape fixture (mirrors react-app's). Exercises
 * the prop names a Qwen3.6 drone naturally emits — shadcn/radix/chakra/
 * mantine vocab. tsc compiles this if the scaffold's UI components meet
 * drone vocabulary; iterate the COMPONENT, not the fixture.
 *
 * Picked up by tsc via tsconfig include `__fixtures__`. Not in vite's
 * import graph so it doesn't bundle.
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
  ColorPicker,
  Dialog,
  Dropdown,
  Flex,
  GlowCard,
  GradientText,
  Heading,
  Input,
  Marquee,
  NotificationCenter,
  Parallax,
  Progress,
  RichTextEditor,
  ScrollReveal,
  Select,
  Skeleton,
  Slideshow,
  StarRating,
  Switch,
  Text,
  Timeline,
  Tooltip,
  TypeWriter,
} from "../src/components/ui"
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
      <Box padding={4} bg="bg-1" bordered>
        <Flex direction="column" spacing={4} inline>
          <Flex direction="row" gap={4} align="center" justify="between">
            <Heading level={1} size="5xl" weight="bold" color="primary">Title</Heading>
            <Heading level={2} size="4xl" as="h2">Subtitle</Heading>
          </Flex>
        </Flex>
      </Box>

      <Text size="xs" muted>tiny muted</Text>
      <Text size="4xl" weight="semibold" color="muted">big</Text>
      <GradientText as="h1" size="6xl" from="#f06" to="#0cf" animate>Headline</GradientText>

      <Button variant="primary" size="md">Primary</Button>
      <Button variant="solid" size="xs">Solid extra small</Button>
      <Button variant="subtle" size="xl" loading disabled fullWidth>Subtle</Button>
      <Button variant="outline" size="md" leftIcon={<span>←</span>} rightIcon={<span>→</span>}>Icons</Button>

      <Card variant="elevated" padding="lg" hoverable interactive>Body</Card>
      <GlowCard glowColor="#4a9eff" intensity={0.8} padding="md">Glow body</GlowCard>

      <Badge variant="success" size="sm" color="green">OK</Badge>
      <Badge variant="destructive" pill outline>Bad</Badge>
      <Badge dot status="online">User</Badge>

      <Avatar fallback="JB" shape="square" size="lg" status="online" />
      <Avatar src="/avatar.jpg" alt="user" size={48} radius="full" />

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

      <Select
        value={option}
        onValueChange={setOption}
        options={[{ value: "a", label: "Apple" }, { value: "b", label: "Banana" }]}
        placeholder="Pick one"
        label="Fruit"
        disabled
        error="Choose one"
      />

      <Switch checked size="lg" disabled color="success" label="Enable" />
      <Switch value={false} onValueChange={() => {}} size="md" />

      <Progress value={42} max={100} size="lg" color="success" showValue />
      <Progress value={75} variant="striped" indeterminate />

      <Skeleton variant="text" lines={3} animation="pulse" />
      <Skeleton variant="rect" width={200} height={120} animation="wave" />
      <Skeleton variant="circle" size={40} />

      <Tooltip content="hello" placement="top" delay={300}><Button>Hover</Button></Tooltip>
      <Tooltip text="legacy" position="bottom"><span>x</span></Tooltip>

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

      <Alert variant="success" title="Saved" icon={<span>✓</span>} dismissible onDismiss={() => {}}>Good</Alert>
      <Alert type="error" title="Oops">Boom</Alert>

      <Accordion
        type="single"
        defaultOpen={0}
        collapsible
        items={[{ title: "Q1", content: "A1" }, { title: "Q2", content: "A2" }]}
      />

      <Marquee speed={20} duration={20} gap={20} pauseOnHover>
        <span>scrolling</span>
      </Marquee>
      <TypeWriter words={["hello", "world"]} loop speed={60} cursor />

      <Slideshow images={["/a.jpg", "/b.jpg"]} autoplay duration={5000} height={300} showDots showArrows />

      <AnimatedCounter from={0} to={1000} duration={1500} format="number" />
      <AnimatedCounter value={42} prefix="$" suffix="k" precision={1} />

      <Calendar
        selected={selected}
        value={selected}
        onSelect={setSelected}
        onChange={setSelected}
        mode="single"
      />

      <StarRating value={rating} onValueChange={setRating} count={5} readOnly={false} />

      <ColorPicker value={color} onChange={setColor} swatches={["#f06","#0cf"]} label="Color" />

      <BeforeAfter
        before="/a.jpg"
        after="/b.jpg"
        beforeImage="/a.jpg"
        afterImage="/b.jpg"
        labelBefore="Before"
        labelAfter="After"
        height={300}
      />

      <AnnouncementBar message="Sale!" text="Sale!" link={{ text: "Shop", href: "#" }} />

      <NotificationCenter
        toasts={[]}
        notifications={[]}
        onDismiss={() => {}}
        position="top-right"
      />

      <Dropdown
        trigger={<Button>Menu</Button>}
        options={[{ label: "One", onClick: () => {} }]}
        items={[{ label: "One", onClick: () => {} }]}
      />

      <Parallax speed={0.5} offset={50}><div>parallax</div></Parallax>
      <ScrollReveal animation="slide-up" direction="up" delay={100} duration={500}>
        <div>reveal</div>
      </ScrollReveal>

      <RichTextEditor
        value={editor}
        defaultValue=""
        onChange={setEditor}
        placeholder="Write..."
        minHeight={150}
      />

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
