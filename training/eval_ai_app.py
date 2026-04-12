#!/usr/bin/env python3
"""eval_ai_app.py — evaluation suite for the ai-app-v1 adapter.

L1: Routing (8 prompts — should pick ai-app-v1)
L2: Scaffold checks (3 — template param, server path, useChat hook)
L3: Error recovery (3 — missing dep, runtime error, syntax error -> file_edit)
L4: Fault probes (18 — DPO pair structure checks)
"""
import argparse, json, os, sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tsunami.adapter_router import pick_adapter


# ── L1: Routing tests ─────────────────────────────────────────────────────────
L1_TESTS = [
    ("AAT01", "Build an AI chatbot.", "ai-app-v1"),
    ("AAT02", "Build a customer support bot using OpenAI API.", "ai-app-v1"),
    ("AAT03", "Build a writing assistant app with Claude.", "ai-app-v1"),
    ("AAT04", "Build a streaming chat app powered by Claude API.", "ai-app-v1"),
    ("AAT05", "Chat with GPT app — users type, AI streams back replies.", "ai-app-v1"),
    ("AAT06", "Build a code review tool using OpenAI streaming.", "ai-app-v1"),
    # Negatives — these should NOT route to ai-app-v1
    ("AAT07-neg", "Build a realtime chat room with WebSockets.", "!ai-app-v1"),
    ("AAT08-neg", "Build a fullstack todo app with database.", "!ai-app-v1"),
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
L2_CHECKS = [
    ("AAS01", 'project_init', 'template.*ai-app', "scaffold: project_init uses template='ai-app'"),
    ("AAS02", r'file_write.*server/index\.js', None, "scaffold: first file_write targets server/index.js"),
    ("AAS03", 'useChat', None, "scaffold: App.tsx imports useChat hook"),
]


def run_l2():
    print("\n=== L2: Scaffold pattern checks (training-data baseline) ===")
    sft_path = "workspace/training_data/ai_app_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: ai_app_sft_v1.jsonl not found")
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
def run_l3():
    """Check that error recovery uses file_edit not file_read after build errors."""
    print("\n=== L3: Error recovery patterns ===")
    sft_path = "workspace/training_data/ai_app_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: ai_app_sft_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(sft_path) as f:
        examples = [json.loads(l) for l in f if l.strip()]

    error_examples = [ex for ex in examples if "error_recovery" in ex.get("source", "")]
    for ex in error_examples:
        text = ex.get("text", "").lower()
        has_error = any(e in text for e in ("cannot find module", "syntaxerror", "typeerror", "error:"))
        has_edit = "file_edit" in text
        no_read_after_error = not re.search(r'(cannot find module|error:).*?file_read', text, re.DOTALL)
        ok = has_error and has_edit and no_read_after_error
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        src = ex.get("source", "?")
        print(f"  {status} AAER: {src}: has_error={has_error} has_edit={has_edit} no_read_after_error={no_read_after_error}")

    if not error_examples:
        print("  SKIP: no error recovery examples found in SFT data")

    return passed, failed


# ── L4: DPO fault probes ──────────────────────────────────────────────────────
def run_l4():
    print("\n=== L4: DPO fault probes ===")
    dpo_path = "workspace/training_data/ai_app_dpo_v1.jsonl"
    if not os.path.exists(dpo_path):
        print("  SKIP: ai_app_dpo_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(dpo_path) as f:
        pairs = [json.loads(l) for l in f if l.strip()]

    for p in pairs:
        src = p.get("source_bug", "?")
        chosen = p.get("chosen", "")
        rejected = p.get("rejected", "")

        if src.startswith("AAF01"):
            ok = "ai-app" in chosen and ("fullstack" in rejected or "react-app" in rejected)
        elif src.startswith("AAF02"):
            ok = "server/index.js" in chosen and \
                 ("App.tsx" in rejected or "src/App" in rejected)
        elif src.startswith("AAF03"):
            ok = ("getReader" in chosen or "delta" in chosen or "sse" in chosen.lower() or "stream" in chosen.lower()) and \
                 ("res.json()" in rejected or "await res.json" in rejected or "json()" in rejected)
        elif src.startswith("AAF04"):
            ok = ("process.env" in chosen or "server" in chosen.lower() or "proxy" in chosen.lower()) and \
                 ("VITE_" in rejected or "hardcode" in rejected.lower() or "directly" in rejected.lower() or "sk-" in rejected)
        elif src.startswith("AAF05"):
            ok = "undertow" in chosen and "undertow" not in rejected
        elif src.startswith("AAF06"):
            ok = "file_edit" in chosen and "file_read" in rejected
        else:
            ok = True

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
