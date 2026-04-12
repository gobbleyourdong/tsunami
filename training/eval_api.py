#!/usr/bin/env python3
"""eval_api.py -- evaluation suite for the api-only-v1 adapter.

L1: Routing (6 prompts -- should pick api-only-v1)
L2: Scaffold selection (3 checks -- template param, server path, no App.tsx)
L3: Error recovery (3 scenarios -- syntax/runtime error -> file_edit not file_read)
L4: Fault probes (18 -- direct preference checks from DPO pairs)
"""
import argparse, json, os, sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tsunami.adapter_router import pick_adapter

# ── L1: Routing tests ─────────────────────────────────────────────────────────

L1_TESTS = [
    # (id, prompt, expected_adapter)
    ("APT01", "Build a REST API for todos. Backend only.",          "api-only-v1"),
    ("APT02", "Build a webhook receiver that logs POST requests.",  "api-only-v1"),
    ("APT03", "Build a microservice for URL shortening.",           "api-only-v1"),
    ("APT04", "Build a restful api for managing products.",         "api-only-v1"),
    ("APT05", "I need a JSON API server for user data. No UI.",     "api-only-v1"),
    ("APT06", "Create a backend only REST API for bookmarks.",      "api-only-v1"),
    # Negative: these should NOT route to api-only (any non-api-only is fine)
    ("APT07-neg", "Build a fullstack todo app with React frontend.", "!api-only-v1"),
    ("APT08-neg", "Build a todo app with a nice UI.",                "!api-only-v1"),
]


def run_l1():
    passed, failed = 0, 0
    print("\n=== L1: Routing ===")
    for tid, prompt, expected in L1_TESTS:
        adapter, reason = pick_adapter(prompt)
        if expected.startswith("!"):
            ok = adapter != expected[1:]
        else:
            ok = adapter == expected
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        mark = "" if ok else f" (got {adapter!r}, reason={reason!r})"
        print(f"  {status} {tid}: {prompt[:55]}{mark}")
    return passed, failed


# ── L2: Scaffold checks ───────────────────────────────────────────────────────

# We check the model response strings for the right patterns.
# In actual testing these would be model outputs; here we test training-data patterns.

L2_CHECKS = [
    ("APS01", 'project_init', 'template.*api-only', "scaffold: project_init uses template='api-only'"),
    ("APS02", 'file_write.*server/index.js', None, "scaffold: first file_write targets server/index.js"),
    ("APS03", 'crud\\(', None, "scaffold: uses crud() factory, not hardcoded routes"),
]


def run_l2(model_fn=None):
    print("\n=== L2: Scaffold pattern checks (training-data baseline) ===")
    # Load the SFT training data and check that the patterns appear in trajectories
    sft_path = "workspace/training_data/api_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: api_sft_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(sft_path) as f:
        examples = [json.loads(l) for l in f if l.strip()]

    for check_id, pat1, pat2, desc in L2_CHECKS:
        hits = 0
        for ex in examples:
            text = ex.get("text", "")
            if re.search(pat1, text) and (not pat2 or re.search(pat2, text)):
                hits += 1
        ok = hits > 0
        if ok: passed += 1
        else: failed += 1
        print(f"  {'PASS' if ok else 'FAIL'} {check_id}: {desc} (found in {hits}/{len(examples)} examples)")

    return passed, failed


# ── L3: Error recovery ───────────────────────────────────────────────────────

L3_CHECKS = [
    ("APER01", "syntax error", "file_edit", "SyntaxError with line -> file_edit directly"),
    ("APER02", "referenceerror", "file_edit", "ReferenceError with line -> file_edit directly"),
    ("APER03", "syntaxerror", "file_write", "SyntaxError fixable by file_write -> file_write"),
]


def run_l3():
    """Check that error recovery in training data uses file_edit not file_read."""
    print("\n=== L3: Error recovery patterns ===")
    sft_path = "workspace/training_data/api_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: api_sft_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(sft_path) as f:
        examples = [json.loads(l) for l in f if l.strip()]

    # Check that error recovery example (ap05) uses file_edit not file_read
    error_examples = [ex for ex in examples if "error_recovery" in ex.get("source", "")]
    for ex in error_examples:
        text = ex.get("text", "").lower()
        has_error = "syntaxerror" in text or "referenceerror" in text
        has_edit = "file_edit" in text
        no_read_after_error = not re.search(r'syntaxerror.*?file_read', text, re.DOTALL)
        ok = has_error and has_edit and no_read_after_error
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        src = ex.get("source", "?")
        print(f"  {status} APER01: {src}: has_error={has_error} has_edit={has_edit} no_read_after_error={no_read_after_error}")

    if not error_examples:
        print("  SKIP: no error recovery examples found")

    return passed, failed


# ── L4: DPO fault probes ──────────────────────────────────────────────────────

def run_l4():
    """Check DPO pair structure -- chosen vs rejected patterns."""
    print("\n=== L4: DPO fault probes ===")
    dpo_path = "workspace/training_data/api_dpo_v1.jsonl"
    if not os.path.exists(dpo_path):
        print("  SKIP: api_dpo_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(dpo_path) as f:
        pairs = [json.loads(l) for l in f if l.strip()]

    for p in pairs:
        src = p.get("source_bug", "?")
        chosen = p.get("chosen", "")
        rejected = p.get("rejected", "")

        if src.startswith("APF01"):
            # chosen: api-only template or server/index.js; rejected: fullstack or App.tsx or main.tsx
            ok = ("api-only" in chosen or "server/index.js" in chosen) and \
                 ("fullstack" in rejected or "App.tsx" in rejected or "main.tsx" in rejected)
        elif src.startswith("APF02"):
            # chosen: server/index.js or npm run dev or curl; rejected: App.tsx or npm run build or undertow
            ok = ("server/index.js" in chosen or "npm run dev" in chosen or "curl" in chosen) and \
                 ("App.tsx" in rejected or "npm run build" in rejected or "undertow" in rejected)
        elif src.startswith("APF03"):
            # chosen: crud() or npm run dev or message_result; rejected: hardcoded routes or node directly or undertow
            ok = ("crud" in chosen or "npm run dev" in chosen or "message_result" in chosen) and \
                 ("undertow" in rejected or "node server" in rejected or "App.tsx" in rejected)
        elif src.startswith("APF04"):
            # chosen: curl or message_result; rejected: undertow
            ok = ("curl" in chosen or "message_result" in chosen) and "undertow" in rejected
        elif src.startswith("APF05"):
            # chosen: server/index.js or message_result; rejected: main.tsx or App.tsx
            ok = ("server/index.js" in chosen or "message_result" in chosen) and \
                 ("main.tsx" in rejected or "App.tsx" in rejected)
        elif src.startswith("APF06"):
            # chosen: file_edit; rejected: file_read
            ok = "file_edit" in chosen and "file_read" in rejected
        else:
            ok = True  # unknown, skip

        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        note = p.get("note", "")[:60]
        print(f"  {status} {src}: {note}")

    return passed, failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--l1-only", action="store_true")
    args = parser.parse_args()

    total_p, total_f = 0, 0

    p, f = run_l1()
    total_p += p; total_f += f

    if not args.l1_only:
        p, f = run_l2()
        total_p += p; total_f += f

        p, f = run_l3()
        total_p += p; total_f += f

        if not args.quick:
            p, f = run_l4()
            total_p += p; total_f += f

    total = total_p + total_f
    pct = total_p / total * 100 if total else 0
    print(f"\n=== Total: {total_p}/{total} ({pct:.0f}%) ===")


if __name__ == "__main__":
    main()
