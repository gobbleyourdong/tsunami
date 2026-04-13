# Tsunami training pod setup

Minimum to run `bash training/sweep.sh N` end-to-end (train + merge + serve + full L1-L5 eval):

```bash
# 1. clone repo
git clone https://github.com/gobbleyourdong/tsunami.git ark
cd ark

# 2. python deps
pip install --break-system-packages -r requirements.txt           # runtime + playwright
pip install --break-system-packages -r requirements-train.txt     # unsloth + trl + ...

# 3. system deps
apt-get update && apt-get install -y nodejs npm                   # L5 builds run `npm` / vite
playwright install chromium                                       # undertow QA tool
playwright install-deps chromium                                  # chromium shared libs

# 4. dataset (workspace/ is gitignored — scp from local or pull from cloud)
mkdir -p workspace/training_data
scp local:/path/to/champion.jsonl workspace/training_data/

# 5. run sweep
bash training/sweep.sh 5     # N = number of GPUs
```

## What each layer of eval needs

| Layer | What it executes | System deps needed |
|---|---|---|
| L1 format | sends prompts, parses tool calls — fake tool results | none |
| L2 scaffold | same | none |
| L3 recovery | same | none |
| L4 hackfree | same | none |
| L5 integration | **real agent loops** — invokes shell_exec, file_write, undertow, riptide, etc | **node, npm, chromium (playwright)** |

L1-L4 are pure model-quality measurements and run on any host with python deps. L5 only works on hosts with the system deps above. Skipping L5 is valid if you only care about tool-call format quality.

## Debug-before-sweep recipe

The trap from 2026-04-13: a 3-step training-only "debug" passes but L5 still fails because npm/playwright were never tested. Always include one L5 prompt in any debug:

```bash
# fast end-to-end sanity (~10 min)
python3 training/train.py --max-steps 3 --merge --output models/debug
python3 tsunami/serve_transformers.py --model models/debug-merged --port 9999 --image-model none &
SPID=$!
# wait for health
for i in {1..30}; do curl -s -m 2 http://localhost:9999/health >/dev/null && break; sleep 5; done
python3 training/eval.py --endpoint http://localhost:9999 --layers integration --output /tmp/debug_eval.json
kill $SPID
```

If the integration eval gets even one PASS, the env is set up. Then fire the real sweep.
