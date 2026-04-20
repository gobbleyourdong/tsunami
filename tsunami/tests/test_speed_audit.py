"""Meta-test: the audit itself should be green.

If this test fails the speed safeguards regressed. Read `python3 -m
tsunami.speed_audit` output for the failure list, fix the source, then
re-run.
"""

from tsunami.speed_audit import run_audit


def test_all_safeguards_present():
    checks = run_audit()
    missing = [f"L{c.layer} {c.name}" for c in checks if not c.present]
    assert not missing, (
        "Agentic-speed safeguards regressed. Missing layers:\n  "
        + "\n  ".join(missing)
        + "\n\nRun `python3 -m tsunami.speed_audit` for details."
    )


def test_all_layers_tracked():
    """If someone adds a safeguard they should extend the audit."""
    checks = run_audit()
    # 12 entries covering 11 logical layers of defense. Changing this asserts
    # the audit stays in sync with the codebase's advertised speed net.
    assert len(checks) == 12


def test_layer_fingerprints_unique():
    """Each fingerprint should be specific enough to only match its layer."""
    checks = run_audit()
    seen = set()
    for c in checks:
        assert c.fingerprint not in seen, (
            f"duplicate fingerprint across layers: {c.fingerprint!r}"
        )
        seen.add(c.fingerprint)
