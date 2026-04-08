# Attempt 004: Why Can't We Reach Compile on L5?

## The Failure Chain

```
Model generates file_write{content:"...code..."}  ← NO PATH ARG
       ↓
Agent validation: "Missing required parameter: path"
       ↓
Error returned to model as tool result
       ↓
Model retries file_write{content:"...code..."} ← STILL NO PATH
       ↓
Loop: 10-30x file_write without path → timeout
       ↓
files_written = 0, compiled = False
```

## The Path Resolution is FINE

The `_resolve_path` function in `filesystem.py` handles all cases correctly:
- `src/App.tsx` → finds most recent project → `deliverables/X/src/App.tsx` ✓
- `deliverables/X/src/App.tsx` → resolves to workspace → `/tmp/tsunami_eval/deliverables/X/src/App.tsx` ✓
- `workspace/deliverables/X/...` → strips workspace prefix → correct ✓

**The path resolution never runs because the model omits the path argument entirely.**

## The NUMBER

In the v5r 56% run (5/9 pass):
- 5 PASS: model included `path` arg → file written → compiled → delivered
- 3 FAIL with files=0: model omitted `path` arg → validation error → 0 files
- 1 FAIL with compiled=True: model included path, compiled, but timed out

**3/4 failures = model omits path argument. This is the single bottleneck.**

## Why Does the Model Omit Path?

The Gemma 4 native format for file_write is:
```
<|tool_call>call:file_write{content:<|"|>...code...<|"|>,path:<|"|>deliverables/X/src/App.tsx<|"|>}<tool_call|>
```

Args are alphabetically sorted: `content` comes before `path`. The model generates `content` first (which is very long — full React component code), then needs to generate `path` after. With a 4B model at 16K context, after generating 200+ tokens of code content, it sometimes "forgets" to add the path argument and closes the tool call.

**This is a model capacity issue at inference time, not a training data issue.**

## Possible Fixes (Ranked)

1. **Reorder args in training data**: put `path` BEFORE `content` so it's generated first
   - Risk: breaks alphabetical ordering convention
   - Benefit: model generates short path string first, then long content

2. **Shorter code in training examples**: reduce content length so model has more
   capacity to remember the path arg
   - Risk: teaches model to write shorter (worse) code

3. **Agent-side: if file_write has content but no path, auto-infer path instead of rejecting**
   - The auto-fix code exists but requires `self._project_init_called`
   - In pre-scaffold builds, project_init isn't called → auto-fix doesn't fire

4. **Increase context window**: more room for the model to hold both content and path
   - Already at 16K, could try 32K

## Recommendation

**Fix #1 is the most promising.** Put path before content in all training examples.
The model generates `path:<|"|>deliverables/X/src/App.tsx<|"|>` (short, ~30 tokens)
FIRST, then `content:<|"|>...long code...<|"|>`. This way the path is committed
before the content uses up model capacity.

This is a DATA fix, not a hack. The arg order in Gemma 4 native format is
convention (alphabetical), not a hard requirement. The tool call parser handles
any order.
