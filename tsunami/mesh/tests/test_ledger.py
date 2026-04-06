"""Tests for Layer 4: Ledger."""

import tempfile
from pathlib import Path

from megalan.ledger import Ledger, TimeCard


def test_clock_in_out():
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("worker1", Path(d))
        ledger.clock_in("job1", "worker1", "requestor1")
        assert "job1" in ledger.timecards

        credits = ledger.clock_out("job1", "result_hash", capability=50.0)
        assert credits > 0
        assert ledger.timecards["job1"].result_hash == "result_hash"


def test_verify_credits_worker():
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("worker1", Path(d))
        ledger.clock_in("job1", "worker1", "requestor1")
        ledger.clock_out("job1", "hash", capability=10.0)
        ledger.verify("job1", ok=True)
        assert ledger.balance > 0
        assert ledger.timecards["job1"].verified


def test_verify_credits_requestor():
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("requestor1", Path(d))
        ledger.clock_in("job1", "worker1", "requestor1")
        ledger.clock_out("job1", "hash", capability=10.0)
        ledger.verify("job1", ok=True)
        assert ledger.balance < 0  # requestor pays


def test_dispute():
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("worker1", Path(d))
        ledger.clock_in("job1", "worker1", "requestor1")
        ledger.clock_out("job1", "hash", capability=10.0)
        ledger.verify("job1", ok=False)
        assert ledger.balance == 0  # no credit for disputed work
        assert ledger.timecards["job1"].disputed


def test_summary():
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("worker1", Path(d))
        s = ledger.summary()
        assert s["balance"] == 0
        assert s["jobs_completed"] == 0
        assert s["transactions"] == 0


def test_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d)
        ledger = Ledger("node1", path)
        ledger.clock_in("job1", "node1", "req1")
        ledger.clock_out("job1", "hash", capability=10.0)
        ledger.verify("job1", ok=True)
        ledger._save()

        ledger2 = Ledger("node1", path)
        assert ledger2.balance == ledger.balance
        assert "job1" in ledger2.timecards


def test_job_type_multipliers():
    """Verify training jobs earn 3x more than tsunami_agent jobs."""
    with tempfile.TemporaryDirectory() as d:
        ledger = Ledger("w", Path(d))

        # Manually set clock_in time to control duration
        ledger.clock_in("j1", "w", "r")
        ledger.timecards["j1"].clock_in -= 10  # fake 10 seconds of work
        c1 = ledger.clock_out("j1", "h", capability=10.0, job_type="tsunami_agent")

        ledger.clock_in("j2", "w", "r")
        ledger.timecards["j2"].clock_in -= 10  # same 10 seconds
        c2 = ledger.clock_out("j2", "h", capability=10.0, job_type="training")

        # Training multiplier is 3.0, tsunami_agent is 1.0
        assert abs(c2 / c1 - 3.0) < 0.1
