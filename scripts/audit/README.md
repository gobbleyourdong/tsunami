# audit — production-firing audit tool

Reference implementation of the Sigma Method v10 principle
**Production-Firing Audit**: *a shipped fix is not proven until its
signature fires in a real session trace.*

## Files

- `audit_production.py` — scans `workspace/.history/session_*.jsonl` for
  each registered fix's signature string; reports hits per fix, flags
  `expect_nonzero=True` entries with zero hits as dead-code-in-waiting.
- `fix_registry.jsonl` — one row per shipped fix:
  `{slug, sha, signature, expect_nonzero, note}`. The signature is the
  distinctive string the fix emits when it fires (gate error text, log
  line, tailored reject message).

## Usage

```bash
python3 scripts/audit/audit_production.py                # last 80 sessions
python3 scripts/audit/audit_production.py --since 200    # wider window
python3 scripts/audit/audit_production.py --slug scaffold_first_gate_hoist
python3 scripts/audit/audit_production.py --json         # machine-readable
```

## When to add a row

Every fix whose runtime intent is `expect_nonzero` (fires at least once
when the target pattern occurs) should be registered with its signature
before the commit lands, or at the next audit pass. Refactors and
predicate-only changes that don't emit a distinctive signature can be
registered with `expect_nonzero=false` + a note explaining why.

## Background

Originates from the 2026-04-20 overnight campaign: three scaffold-first
gate commits over two weeks were silently dead code because the
predicate they keyed on was renamed at provisioning time. Unit tests
kept passing (fixtures preserved the name); production never ran the
gate. The audit tool was built to catch this class of bug before it
accumulates. Case study: `~/sigma/case_studies/dead_fix_claims_001.md`.
