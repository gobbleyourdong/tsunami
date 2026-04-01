# Testing — The Undertow

The plan is the test. Describe what the user does, then the undertow walks that journey.

## The plan IS the test spec

Before building, write a plan that describes the user experience step by step.
This same plan becomes the test:

```markdown
# Plan: Pinball Game

The player charges the plunger by holding Space.
They release Space and the ball launches up the table.
The ball falls due to gravity, bouncing off bumpers.
Bumper hits increase the score.
The player uses Left/Right arrows to flip the paddles.
The paddles deflect the ball back up.
If the ball falls through the drain, a life is lost.
After 3 lives, game over. Press R to restart.
```

Each sentence is a testable assertion. The undertow verifies them:
- "charges the plunger by holding Space" → press Space, check if something changes
- "ball launches" → after Space, check for motion
- "falls due to gravity" → scene should be animated without input
- "score increases" → read score element before and after bumper area activity
- "Left/Right arrows flip paddles" → press arrow, check if pixels change

## Call undertow with the plan as the expectation

```
undertow(path="index.html", expect="pinball game where Space launches ball, arrows move flippers, ball bounces off bumpers, score increases on hits")
```

The undertow auto-generates levers from the HTML + adds motion detection.
It reports what it saw. You fix what failed. Call undertow again. Repeat.

## Fix loop — keep going until it plays right

1. Read failures
2. Fix the specific issue
3. Test again
4. Repeat until the core journey works

Don't deliver until motion is detected and the core interaction loop works.
