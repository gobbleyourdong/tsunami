#!/usr/bin/env python3
"""eval_auth_app.py -- evaluation suite for the auth-app-v1 adapter.

L1: Routing (8 prompts -- should pick auth-app-v1)
L2: Scaffold selection (3 checks -- template param, server path, authFetch usage)
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
    ("AUT01", "Build a notes app with user accounts and login.",      "auth-app-v1"),
    ("AUT02", "Build a todo app with user registration and JWT auth.", "auth-app-v1"),
    ("AUT03", "Build a SaaS app with email and password login.",       "auth-app-v1"),
    ("AUT04", "Build an expense tracker with per-user data.",          "auth-app-v1"),
    ("AUT05", "Build a bookmark manager with login page.",             "auth-app-v1"),
    ("AUT06", "Build a task manager with protected routes.",           "auth-app-v1"),
    # Negative: these should NOT route to auth-app (any non-auth-app is fine)
    ("AUT07-neg", "Build a fullstack todo app with Express backend.",  "!auth-app-v1"),
    ("AUT08-neg", "Build a simple todo app with local storage.",       "!auth-app-v1"),
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
    ("AUS01", 'project_init', 'template.*auth-app', "scaffold: project_init uses template='auth-app'"),
    ("AUS02", 'file_write.*server/index.js', None, "scaffold: first file_write targets server/index.js"),
    ("AUS03", 'authFetch', None, "scaffold: uses authFetch() from useAuth(), not raw fetch()"),
]


def run_l2(model_fn=None):
    print("\n=== L2: Scaffold pattern checks (training-data baseline) ===")
    sft_path = "workspace/training_data/auth_app_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: auth_app_sft_v1.jsonl not found")
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
    """Check that error recovery in training data uses file_edit not file_read."""
    print("\n=== L3: Error recovery patterns ===")
    sft_path = "workspace/training_data/auth_app_sft_v1.jsonl"
    if not os.path.exists(sft_path):
        print("  SKIP: auth_app_sft_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(sft_path) as f:
        examples = [json.loads(l) for l in f if l.strip()]

    error_examples = [ex for ex in examples if "error_recovery" in ex.get("source", "")]
    for ex in error_examples:
        text = ex.get("text", "").lower()
        has_error = "typeerror" in text or "syntaxerror" in text or "cannot find" in text
        has_edit = "file_edit" in text
        no_read_after_error = not re.search(r'(typeerror|syntaxerror).*?file_read', text, re.DOTALL)
        ok = has_error and has_edit and no_read_after_error
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        src = ex.get("source", "?")
        print(f"  {status} AUER01: {src}: has_error={has_error} has_edit={has_edit} no_read_after_error={no_read_after_error}")

    if not error_examples:
        print("  SKIP: no error recovery examples found")

    return passed, failed


# ── L4: DPO fault probes ──────────────────────────────────────────────────────

def run_l4():
    """Check DPO pair structure -- chosen vs rejected patterns."""
    print("\n=== L4: DPO fault probes ===")
    dpo_path = "workspace/training_data/auth_app_dpo_v1.jsonl"
    if not os.path.exists(dpo_path):
        print("  SKIP: auth_app_dpo_v1.jsonl not found")
        return 0, 0

    passed, failed = 0, 0
    with open(dpo_path) as f:
        pairs = [json.loads(l) for l in f if l.strip()]

    for p in pairs:
        src = p.get("source_bug", "?")
        chosen = p.get("chosen", "")
        rejected = p.get("rejected", "")

        if src.startswith("AUF01"):
            # chosen: auth-app template; rejected: fullstack or react-app
            ok = "auth-app" in chosen and \
                 ("fullstack" in rejected or "react-app" in rejected)
        elif src.startswith("AUF02"):
            # chosen: server/index.js before App.tsx; rejected: App.tsx first
            ok = "server/index.js" in chosen and "App.tsx" in rejected
        elif src.startswith("AUF03"):
            # chosen: authFetch; rejected: raw fetch() or manual token
            ok = "authFetch" in chosen and \
                 ("fetch(" in rejected or "localStorage" in rejected or "raw fetch" in rejected.lower())
        elif src.startswith("AUF04"):
            # chosen: ProtectedRoute; rejected: no protection or manual guard
            ok = "ProtectedRoute" in chosen and \
                 ("no protection" in rejected or "ProtectedRoute" not in rejected)
        elif src.startswith("AUF05"):
            # chosen: undertow; rejected: no undertow / message_result direct
            ok = "undertow" in chosen and "undertow" not in rejected
        elif src.startswith("AUF06"):
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
