/**
 * Landing-page composition fixture: hero, features grid, pricing tiers,
 * waitlist form, social proof, CTA. Same widening rule as the shared
 * fixture — if a prop fails, fix the COMPONENT, not this file.
 */
import {
  AnnouncementBar,
  Avatar,
  Badge,
  Button,
  Card,
  Flex,
  GradientText,
  GlowCard,
  Heading,
  Input,
  Marquee,
  Parallax,
  ScrollReveal,
  StarRating,
  Text,
  TypeWriter,
} from "../src/components/ui"
import Box from "../src/components/ui/Box"

function Nav() {
  return (
    <Flex justify="between" align="center" gap={4}>
      <GradientText as="span" size="2xl" from="#4a9eff" to="#a070f0">Brand</GradientText>
      <Flex gap={4} align="center">
        <Button variant="ghost" size="sm">Pricing</Button>
        <Button variant="ghost" size="sm">Docs</Button>
        <Button variant="primary" size="sm">Sign in</Button>
      </Flex>
    </Flex>
  )
}

function Hero() {
  return (
    <Parallax speed={0.6} offset={20}>
      <Flex direction="col" align="center" gap={4}>
        <Badge variant="primary" pill size="sm">v2.0 — now in beta</Badge>
        <GradientText as="h1" size="7xl" from="#f06" via="#a0f" to="#0cf" animate>
          The fastest way to ship.
        </GradientText>
        <Text size="xl" color="muted" as="p">
          A modern toolkit for builders who care about details.
        </Text>
        <TypeWriter words={["No setup.", "No fluff.", "Just ship."]} loop speed={50} cursor />
        <Flex gap={3}>
          <Button variant="primary" size="xl">Start free</Button>
          <Button variant="outline" size="xl" leftIcon={<span>▶</span>}>Watch demo</Button>
        </Flex>
      </Flex>
    </Parallax>
  )
}

function Features() {
  const features = [
    { icon: "⚡", title: "Fast", body: "Sub-100ms cold starts." },
    { icon: "🛡", title: "Safe", body: "Type-checked end to end." },
    { icon: "🌐", title: "Global", body: "Edge-deployed by default." },
    { icon: "🧩", title: "Modular", body: "Plug components as needed." },
  ]
  return (
    <Box padding={6}>
      <Heading level={2} size="3xl" weight="bold">Why teams pick us</Heading>
      <Flex wrap gap={4}>
        {features.map(f => (
          <GlowCard key={f.title} glowColor="#4a9eff" intensity={0.6} padding="lg">
            <Text size="3xl">{f.icon}</Text>
            <Heading level={3} size="lg">{f.title}</Heading>
            <Text muted size="sm">{f.body}</Text>
          </GlowCard>
        ))}
      </Flex>
    </Box>
  )
}

function Pricing() {
  return (
    <Flex gap={4} wrap>
      {[
        { tier: "Starter", price: "$0",  popular: false },
        { tier: "Pro",     price: "$29", popular: true  },
        { tier: "Team",    price: "$99", popular: false },
      ].map(p => (
        <Card key={p.tier} variant={p.popular ? "elevated" : "outline"} padding="lg" hoverable>
          <Flex justify="between" align="center">
            <Heading level={3} size="xl">{p.tier}</Heading>
            {p.popular && <Badge variant="primary" pill>Popular</Badge>}
          </Flex>
          <Heading level={2} size="4xl" weight="extrabold">{p.price}</Heading>
          <Text size="sm" muted>per seat / month</Text>
          <Button fullWidth variant={p.popular ? "primary" : "outline"}>Choose {p.tier}</Button>
        </Card>
      ))}
    </Flex>
  )
}

function Waitlist() {
  return (
    <Card variant="elevated" padding="xl">
      <Heading level={2} size="2xl">Join the waitlist</Heading>
      <Text muted size="sm">We&apos;ll email when your account is ready.</Text>
      <Flex gap={2}>
        <Input label="Email" placeholder="you@example.com" type="email" fullWidth />
        <Button variant="primary" size="md">Join</Button>
      </Flex>
    </Card>
  )
}

function SocialProof() {
  return (
    <Box>
      <Heading level={2} size="2xl">Loved by teams</Heading>
      <Marquee speed={30} pauseOnHover gap={32}>
        {Array.from({ length: 6 }, (_, i) => (
          <Flex key={i} align="center" gap={3}>
            <Avatar fallback={`U${i}`} size="md" status="online" />
            <Text muted size="sm">&quot;changed how we ship&quot;</Text>
            <StarRating value={5} max={5} readOnly />
          </Flex>
        ))}
      </Marquee>
    </Box>
  )
}

function CTA() {
  return (
    <ScrollReveal animation="slide-up" delay={200} duration={600}>
      <Box padding={8} bg="bg-1" rounded shadow>
        <Flex direction="col" align="center" gap={4}>
          <Heading level={2} size="4xl">Ready to ship?</Heading>
          <Button variant="primary" size="xl">Start free trial</Button>
        </Flex>
      </Box>
    </ScrollReveal>
  )
}

export default function LandingFixture() {
  return (
    <div>
      <AnnouncementBar message="Beta is live — first 100 get lifetime pricing" link={{ text: "Claim", href: "#" }} variant="promo" />
      <Nav />
      <Hero />
      <Features />
      <Pricing />
      <Waitlist />
      <SocialProof />
      <CTA />
    </div>
  )
}
