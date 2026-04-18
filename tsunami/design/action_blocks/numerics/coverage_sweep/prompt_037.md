# Prompt 037 — Edutainment (Math Blaster / typing tutor)

**Pitch:** game-like shell (shoot asteroids, dodge obstacles) requires answering academic questions (math problems, typing words) to progress; increasing difficulty per level; score by correct answers within time.

**Verdict:** **expressible with content-multiplier**

**Proposed design (sketch):**
- archetypes: `player_ship`, `asteroid_with_question_*`, `question_queue`
- mechanics: `QuestionGenerator` (procedurally emit math problem / typing target), `AnswerCheck` (compare player input to expected answer), `ScoreCombos` ✓ (streak correct), `Difficulty` ✓ (harder questions over time), `HUD` (question + timer), `AutoScroll` (v1) or WaveSpawner ✓

**Missing from v0:**
- **`QuestionGenerator`** — emits (question, expected_answer) pairs from a parameterized generator (addition with N digits, verbs in present tense). Content-multiplier (note_009): one generator × N difficulty tiers × N subject topics = thousands of questions.
- **`AnswerCheck`** — input → expected-answer comparison with tolerance (case-insensitive, approximate numeric). Specialized trigger.
- **Question text rendering** — HUD variant with live-updating question widget.

**Forced workarounds:**
- Hand-author each question as a triggerable archetype — defeats the purpose (and scales poorly).
- Use custom component with per-archetype (`question`, `answer`) data — works with generator backing.

**v1 candidates raised:**
- `QuestionGenerator` — text generator with parameter schema (content-multiplier per note_009)
- `AnswerCheck` — input-equals-expected trigger with type tolerance

**Stall note:** edutainment is a **content-multiplier genre**. One
QuestionGenerator + one AnswerCheck + v0 scoring = thousands of
edutainment games (math, typing, language, vocabulary, geography). If
v1 prioritizes content-multipliers per note_009, this is a small
bundle with broad coverage. Not the sexiest genre but has market
viability (classroom software). Low-cost high-value.
