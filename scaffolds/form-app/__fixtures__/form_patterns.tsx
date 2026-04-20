/**
 * Form-app composition fixture: multi-step wizard, validation states,
 * step indicator, conditional fields, submit + success. Drones reach for
 * `error`/`helperText` on Input, `disabled`/`error` on Select, `Progress`
 * for step bars, `Alert` for validation summary.
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
  Progress,
  Select,
  Switch,
  Text,
  Tooltip,
} from "../src/components/ui"
import Box from "../src/components/ui/Box"
import { useState } from "react"

const STEPS = ["Account", "Profile", "Plan", "Confirm"] as const

function StepBar({ step }: { step: number }) {
  const pct = ((step + 1) / STEPS.length) * 100
  return (
    <Box>
      <Flex justify="between" align="center" gap={2}>
        {STEPS.map((label, i) => (
          <Flex key={label} align="center" gap={2}>
            <Badge
              variant={i < step ? "success" : i === step ? "primary" : "secondary"}
              pill
              size="md"
            >
              {i + 1}
            </Badge>
            <Text size="sm" weight={i === step ? "semibold" : "normal"} muted={i > step}>
              {label}
            </Text>
          </Flex>
        ))}
      </Flex>
      <Progress value={pct} size="sm" color="primary" showValue />
    </Box>
  )
}

function AccountStep({ onNext }: { onNext: () => void }) {
  const [email, setEmail] = useState("")
  const [pw, setPw] = useState("")
  const emailErr = email && !/^\S+@\S+\.\S+$/.test(email) ? "Invalid email" : ""
  const pwErr = pw && pw.length < 8 ? "At least 8 characters" : ""
  return (
    <Flex direction="col" gap={3}>
      <Heading level={2} size="2xl">Create your account</Heading>
      <Input
        label="Email"
        placeholder="you@example.com"
        type="email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        error={emailErr}
        helperText="We'll never share this."
        size="md"
        fullWidth
      />
      <Input
        label="Password"
        type="password"
        value={pw}
        onChange={e => setPw(e.target.value)}
        error={pwErr}
        helperText="At least 8 characters."
        size="md"
        fullWidth
      />
      <Flex justify="end">
        <Button variant="primary" onClick={onNext} disabled={!!emailErr || !!pwErr || !email || !pw}>
          Continue
        </Button>
      </Flex>
    </Flex>
  )
}

function ProfileStep({ onPrev, onNext }: { onPrev: () => void; onNext: () => void }) {
  const [country, setCountry] = useState("US")
  const [name, setName] = useState("")
  const [marketing, setMarketing] = useState(true)
  return (
    <Flex direction="col" gap={3}>
      <Heading level={2} size="2xl">Tell us about you</Heading>
      <Input label="Full name" value={name} onChange={e => setName(e.target.value)} size="md" fullWidth />
      <Select
        label="Country"
        value={country}
        onValueChange={setCountry}
        options={[
          { value: "US", label: "United States" },
          { value: "CA", label: "Canada" },
          { value: "UK", label: "United Kingdom" },
        ]}
        size="md"
      />
      <Switch
        checked={marketing}
        onCheckedChange={setMarketing}
        label="Send me occasional product updates"
        size="md"
        color="primary"
      />
      <Flex justify="between">
        <Button variant="outline" onClick={onPrev}>Back</Button>
        <Button variant="primary" onClick={onNext} disabled={!name}>Continue</Button>
      </Flex>
    </Flex>
  )
}

function PlanStep({ onPrev, onNext }: { onPrev: () => void; onNext: () => void }) {
  const [plan, setPlan] = useState("pro")
  return (
    <Flex direction="col" gap={3}>
      <Heading level={2} size="2xl">Pick a plan</Heading>
      <Flex gap={3} wrap>
        {[
          { id: "free", name: "Free", price: "$0" },
          { id: "pro", name: "Pro", price: "$29" },
          { id: "team", name: "Team", price: "$99" },
        ].map(p => (
          <Tooltip key={p.id} content={`Pick ${p.name}`}>
            <Card
              variant={plan === p.id ? "elevated" : "outline"}
              padding="lg"
              interactive
              onClick={() => setPlan(p.id)}
            >
              <Heading level={3} size="lg">{p.name}</Heading>
              <Heading level={4} size="2xl" weight="extrabold">{p.price}</Heading>
              {plan === p.id && <Badge variant="success" pill>Selected</Badge>}
            </Card>
          </Tooltip>
        ))}
      </Flex>
      <Flex justify="between">
        <Button variant="outline" onClick={onPrev}>Back</Button>
        <Button variant="primary" onClick={onNext}>Continue</Button>
      </Flex>
    </Flex>
  )
}

function ConfirmStep({ onPrev, onSubmit }: { onPrev: () => void; onSubmit: () => void }) {
  return (
    <Flex direction="col" gap={3}>
      <Heading level={2} size="2xl">Review</Heading>
      <Alert type="info" title="Almost done">Click Submit to create your account.</Alert>
      <Flex justify="between">
        <Button variant="outline" onClick={onPrev}>Back</Button>
        <Button variant="primary" onClick={onSubmit}>Submit</Button>
      </Flex>
    </Flex>
  )
}

function SuccessDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog
      open={open}
      onOpenChange={onClose}
      title="You're in!"
      description="Check your inbox for a verification link."
      size="sm"
      footer={<Button variant="primary" onClick={onClose}>Got it</Button>}
    >
      <Alert variant="success" title="Account created">Welcome aboard.</Alert>
    </Dialog>
  )
}

export default function FormFixture() {
  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  return (
    <Card padding="xl">
      <StepBar step={step} />
      {step === 0 && <AccountStep onNext={() => setStep(1)} />}
      {step === 1 && <ProfileStep onPrev={() => setStep(0)} onNext={() => setStep(2)} />}
      {step === 2 && <PlanStep onPrev={() => setStep(1)} onNext={() => setStep(3)} />}
      {step === 3 && <ConfirmStep onPrev={() => setStep(2)} onSubmit={() => setDone(true)} />}
      <SuccessDialog open={done} onClose={() => setDone(false)} />
    </Card>
  )
}
