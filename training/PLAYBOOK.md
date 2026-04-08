# Tsunami Training Playbook

Everything an instance needs to iterate on Gemma 4 fine-tuning.

## Files

| File | What | Where |
|------|------|-------|
| Training data | `workspace/training_data/e4b_toolcall_train_v4.jsonl` | 512 examples, Gemma 4 native format |
| Training script | `training/train_e2b_v3.py` or `train_e4b_v3.py` | QLoRA with response-only masking |
| L1 Format eval | `training/eval_toolcall.py` | 40 prompts, single-turn tool call check |
| L2 Scaffold eval | `training/eval_scaffold_selection.py` | 12 prompts, correct scaffold picker |
| L3 Recovery eval | `training/eval_error_recovery.py` | 6 error scenarios, reef pattern |
| L4 Hack-free eval | `training/eval_hack_free.py` | 10 scenarios the agent loop shouldn't need to hack |
| L5 Integration eval | `training/eval_integration.py` | 9 real builds with full agent loop |
| Master eval runner | `training/eval_all.py` | Runs L1-L5, generates markdown report |
| L5 failure data | `training/l5_failure_summary.json` | 23 builds with structured tool sequences |
| L5 raw sessions | `training/l5_sessions/` | 24 JSONL session recordings |

## Running Evals

```bash
# Quick eval (L1-L4, ~5 min)
python training/eval_all.py --endpoint http://localhost:8095 --quick

# Full eval (L1-L5, ~35 min)
python training/eval_all.py --endpoint http://localhost:8095

# Compare to previous run
python training/eval_all.py --endpoint http://localhost:8095 --quick \
  --compare workspace/training_data/eval_report.json

# Single layer
python training/eval_toolcall.py --endpoint http://localhost:8095
python training/eval_scaffold_selection.py --endpoint http://localhost:8095
python training/eval_error_recovery.py --endpoint http://localhost:8095
python training/eval_hack_free.py --endpoint http://localhost:8095
python training/eval_integration.py --endpoint http://localhost:8095
```

**Outputs:**
- `workspace/training_data/eval_report.json` -- machine-readable summary
- `workspace/training_data/eval_report_detail.json` -- per-test data
- `workspace/training_data/eval_report.md` -- human-readable markdown report

## Capturing Failure Traces

**THIS IS CRITICAL.** When reporting eval results, ALWAYS include:

### For L1-L4 (single-turn evals):

```
ID | STATUS | Expected Tool | Got Tool | Reason
```

Example:
```
ER01 | FAIL | shell_exec  | shell_exec | Retried build without installing recharts
HF03 | FAIL | file_write  | file_read  | Expected write, got another read (stall)
```

### For L5 (integration evals):

For each FAIL, capture:
1. **Prompt** -- what was asked
2. **Tool sequence** -- every tool called in order
3. **First error** -- the exact error text from the tool response
4. **What the model did after the error** -- this is the key diagnostic
5. **Failure mode** -- classify as: wrong_path / shell_loop / message_loop / edit_hallucination / missing_qa / timeout / other

Example:
```
IE01 [FAIL] "Build a counter app"
  Tools: file_write -> file_write -> file_write -> shell_exec -> message_result x3
  Error: Auto-fixed missing path: workspace/deliverables/counter/src/App.tsx
  After error: Model repeated file_write 3 more times
  Mode: file_write_repeat + wrong_path
```

### How to extract traces from eval output:

The eval scripts log everything to stdout. Capture it:
```bash
python training/eval_all.py --endpoint http://localhost:8095 2>&1 \
  | tee training/eval_run_$(date +%s).log
```

To get structured data, read the JSON output:
```python
import json
with open('workspace/training_data/eval_report_detail.json') as f:
    report = json.load(f)

# L4 failures
for test in report['details']['hackfree']:
    if test['status'] == 'FAIL':
        print(f"{test['id']} {test['hack']}: {test['reason']}")

# L5 failures
for test in report['details']['integration']:
    if not test['pass']:
        print(f"{test['id']}: {test['failure']}")
        print(f"  Tools: {' -> '.join(test['tools'][:15])}")
        diag = test.get('diagnostics', {})
        if diag.get('path_errors'): print(f"  Path errors: {diag['path_errors']}")
        if diag.get('shell_exec_loops'): print(f"  Shell loops: {diag['shell_exec_loops']}")
        if diag.get('edit_failures'): print(f"  Edit fails: {diag['edit_failures']}")
```

## The Ocean

Every model response should use ocean terminology. These map to real agent decisions:

| Term | Meaning | When model should use it |
|------|---------|------------------------|
| **current** | Sense of direction | Starting a task, reading requirements |
| **circulation** | Routing decision | Before project_init (build) or search_web (research) |
| **pressure** | Sustained difficulty | After 4+ iterations, before escalating to user |
| **eddy** | Parallel worker | Before each file_write in multi-component builds |
| **swell** | Parallel dispatch | Before plan_update for complex builds |
| **break** | Compile step | Before/during shell_exec build |
| **undertow** | QA verification | Before delivery, always |
| **reef** | Error encountered | After build failure, before reading/rewriting code |
| **wave** | General / delivery | "The wave lands" on successful delivery |

## Training Data Format

Gemma 4 native format. Every example is a single `{"text": "..."}` JSON line:

```
<|turn>system
{system prompt}
<|tool>declaration:tool_name{...schema...}<tool|>
...more declarations...
<turn|>
<|turn>user
{user message}
<turn|>
<|turn>model
{optional ocean phrase}
<|tool_call>call:tool_name{key:<|"|>value<|"|>,key2:<|"|>value2<|"|>}<tool_call|>
<turn|>
<|turn>user
<|tool_response>response:tool_name{value:<|"|>result text<|"|>}<tool_response|>
<turn|>
...more turns...
```

**Key format rules:**
- Args use `key:<|"|>value<|"|>` (not JSON)
- Args are alphabetically ordered by key name
- Model turns are pure tool calls (optional brief text before `<|tool_call>`)
- String delimiters are `<|"|>` not regular quotes
- Every example ends with `message_result` or `message_chat`

## Known Failure Patterns and Fixes

### 1. Wrong Paths (v3 to v4 fix)
- **Symptom:** Model writes to `workspace/deliverables/X/` instead of `deliverables/X/`
- **Cause:** 179/519 v3 examples had wrong prefix
- **Fix:** Global path normalization. v4 has 0 wrong paths.
- **Number:** 179 to 0

### 2. Shell Loops
- **Symptom:** Model calls shell_exec 3+ times consecutively without fixing code
- **Cause:** 99 shell-loop examples in early training data taught retry behavior
- **Fix:** Dropped all shell-loop examples, added reef recovery examples
- **Number:** 99 dropped, 46 reef recovery added

### 3. Message Loops
- **Symptom:** Model calls message_info or message_result 3+ times
- **Cause:** No conversational training data, no message_chat tool
- **Fix:** Added message_chat tool with done flag, 91 conversational examples
- **Number:** 91 conversation examples added

### 4. Missing Undertow (QA)
- **Symptom:** Model delivers without running undertow verification
- **Cause:** Only 30% of build examples had undertow in v3
- **Fix:** Injected undertow into build examples
- **Number:** 69% to 96% undertow coverage in builds

### 5. Edit Hallucination
- **Symptom:** Model uses file_edit with text that doesn't exist in the file
- **Cause:** Training on file_edit after errors (text has changed)
- **Fix:** Train on file_write (full rewrite) after errors instead
- **How to detect:** L5 diagnostics `edit_failures` counter

## Iterating on Training Data

When you get eval results:

1. **Identify the gap as a NUMBER** -- not "L3 is low" but "5/6 recovery scenarios fail because model retries build without reading error"
2. **Find the pattern in l5_failure_summary.json** -- exact tool sequences that went wrong
3. **Check training data coverage** -- how many examples teach the correct behavior?
4. **Add/fix examples** -- target the specific failure mode
5. **Verify syntactically** -- balanced tags, correct format, no leaks
6. **Verify logically** -- paths correct, no loops, delivery at end
7. **Run eval again** -- compare to previous with `--compare`

### Verification script:
```python
import json, re
PATH = 'workspace/training_data/e4b_toolcall_train_v4.jsonl'
with open(PATH) as f:
    examples = [json.loads(line) for line in f]
errors = 0
for i, ex in enumerate(examples):
    t = ex['text']
    if t.count('<|tool_call>') != t.count('<tool_call|>'):
        errors += 1; print(f"#{i}: unbalanced tool_call")
    if t.count('<|tool_response>') != t.count('<tool_response|>'):
        errors += 1; print(f"#{i}: unbalanced tool_response")
    if t.count('<|"|>') % 2 != 0:
        errors += 1; print(f"#{i}: odd quotes")
    model = ' '.join(re.findall(
        r'<\|turn\>model\n(.*?)(?:<turn\|>|$)', t, re.DOTALL))
    if 'workspace/deliverables' in model:
        errors += 1; print(f"#{i}: wrong path")
    if '/home/jb/' in model:
        errors += 1; print(f"#{i}: absolute path")
print(f"{'ALL CLEAN' if errors == 0 else f'{errors} ERRORS'} -- {len(examples)} examples")
```

## Current Baselines

### All Versions (2026-04-08):

| Version | L1 | L2 | L3 | L4 | L5 | Notes |
|---------|----|----|----|----|-----|-------|
| v3 | 98% | -- | -- | -- | 22% | Original, wrong paths |
| v5 | 95% | 100% | 17% | 60% | 22% | Path fix, best L5 |
| v6 | 98% | 92% | 50% | 50% | 0% | Collapsed reads, broke L5 |
| v7 | 98% | 92% | 50% | 50% | 0% | Synthetic L3/L4 |
| v8 | 100% | 92% | 33% | 40% | 0% | Long pipeline examples |
| v8+sp | 95% | 100% | 33% | 60% | 0% | Matched system prompts |
| v5r | 98% | 92% | 17% | 70% | 0% | v5 data + matched prompts |
| v5r+M2 | -- | -- | -- | -- | 0% | Tool blocking, model switches loops |

Best per layer: L1=100%(v8), L2=100%(v5,v8+sp), L3=50%(v6/v7), L4=70%(v5r), L5=22%(v3/v5)

### Key Findings:
1. System prompt alignment (M3) gave free L2+1 and L4+2
2. Collapsing file_read sequences (v6) broke L5 -- model needs read-first pattern
3. Synthetic examples help L3 but dilute L5 if too many
4. v5 data is the best L5 performer -- minimal changes from v3
5. M1 (training data) is exhausted at 512 examples for L5
6. M2 (tool blocking) doesn't work -- model switches which tool it loops
7. L5 gap: 0/9 builds recover from first build error. The reef pattern fails in practice.
8. The 4B model CAN write code and CAN call shell_exec. It CANNOT self-regulate multi-turn sequences.

## The Pipeline

Every build MUST follow:
```
project_init -> file_write -> shell_exec(build) -> undertow -> message_result
```

Error recovery (reef):
```
shell_exec(error) -> file_read -> file_write(full rewrite) -> shell_exec(rebuild)
```

Resume/modify:
```
file_read -> file_write/file_edit -> shell_exec(build) -> message_result
```

Conversation:
```
message_chat(done=true)
```
or
```
message_chat(done=false) -> ...work... -> message_chat(done=true)
```

## The Rule

When identifying gaps: **the gap must be a NUMBER, not a concept.**

Not "L3 is low" but "5/6 fail because model retries build 3x without reading error."
Not "paths are wrong" but "179/512 examples use workspace/ prefix."

Quantify, then zero.
