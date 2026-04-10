"""Layer 4: Ledger — credit tracking.

Not blockchain. Distributed append-only log.
Each node tracks its own balance + recent transactions it witnessed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("megalan.ledger")


@dataclass
class TimeCard:
    job_id: str
    worker_id: str
    requestor_id: str
    clock_in: float
    clock_out: float = 0
    result_hash: str = ""
    credits: float = 0
    verified: bool = False
    disputed: bool = False


@dataclass
class CreditTx:
    job_id: str
    from_id: str  # requestor
    to_id: str  # worker
    amount: float
    timestamp: float = field(default_factory=time.time)
    witnesses: list[str] = field(default_factory=list)


# Job type multipliers
JOB_MULTIPLIERS = {
    "tsunami_agent": 1.0,
    "inference": 1.5,
    "training": 3.0,
    "static_host": 0.1,
}


class Ledger:
    """Local credit ledger for a node."""

    def __init__(self, node_id: str, data_dir: Path | None = None):
        self.node_id = node_id
        self.balance: float = 0
        self.timecards: dict[str, TimeCard] = {}  # job_id → timecard
        self.transactions: list[CreditTx] = []
        self._data_dir = data_dir or Path.home() / ".megalan" / "ledger"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def clock_in(self, job_id: str, worker_id: str, requestor_id: str):
        self.timecards[job_id] = TimeCard(
            job_id=job_id,
            worker_id=worker_id,
            requestor_id=requestor_id,
            clock_in=time.time(),
        )
        log.info(f"CLOCK_IN: job={job_id[:12]}... worker={worker_id[:12]}...")

    def clock_out(self, job_id: str, result_hash: str, capability: float = 1.0,
                  job_type: str = "tsunami_agent"):
        tc = self.timecards.get(job_id)
        if not tc:
            log.warning(f"CLOCK_OUT for unknown job {job_id[:12]}...")
            return 0

        tc.clock_out = time.time()
        tc.result_hash = result_hash

        duration = tc.clock_out - tc.clock_in
        multiplier = JOB_MULTIPLIERS.get(job_type, 1.0)
        tc.credits = duration * capability * multiplier
        return tc.credits

    def verify(self, job_id: str, ok: bool):
        tc = self.timecards.get(job_id)
        if not tc:
            return

        if ok:
            tc.verified = True
            if tc.worker_id == self.node_id:
                self.balance += tc.credits
                log.info(f"CREDIT +{tc.credits:.2f} for job {job_id[:12]}... (balance: {self.balance:.2f})")
            elif tc.requestor_id == self.node_id:
                self.balance -= tc.credits
                log.info(f"DEBIT -{tc.credits:.2f} for job {job_id[:12]}... (balance: {self.balance:.2f})")

            self.transactions.append(CreditTx(
                job_id=job_id,
                from_id=tc.requestor_id,
                to_id=tc.worker_id,
                amount=tc.credits,
            ))
        else:
            tc.disputed = True
            log.warning(f"DISPUTE: job {job_id[:12]}...")

        self._save()

    def record_witness(self, tx: CreditTx):
        """Record a transaction we witnessed (broadcast from peers)."""
        self.transactions.append(tx)
        if len(self.transactions) % 100 == 0:
            self._save()

    def summary(self) -> dict:
        earned = sum(tx.amount for tx in self.transactions if tx.to_id == self.node_id)
        spent = sum(tx.amount for tx in self.transactions if tx.from_id == self.node_id)
        return {
            "balance": self.balance,
            "total_earned": earned,
            "total_spent": spent,
            "jobs_completed": sum(1 for tc in self.timecards.values() if tc.verified),
            "jobs_disputed": sum(1 for tc in self.timecards.values() if tc.disputed),
            "transactions": len(self.transactions),
        }

    def _save(self):
        data = {
            "node_id": self.node_id,
            "balance": self.balance,
            "timecards": {
                jid: {
                    "job_id": tc.job_id,
                    "worker_id": tc.worker_id,
                    "requestor_id": tc.requestor_id,
                    "clock_in": tc.clock_in,
                    "clock_out": tc.clock_out,
                    "result_hash": tc.result_hash,
                    "credits": tc.credits,
                    "verified": tc.verified,
                    "disputed": tc.disputed,
                }
                for jid, tc in self.timecards.items()
            },
            "transactions": [
                {
                    "job_id": tx.job_id,
                    "from_id": tx.from_id,
                    "to_id": tx.to_id,
                    "amount": tx.amount,
                    "timestamp": tx.timestamp,
                }
                for tx in self.transactions[-1000:]  # keep last 1000
            ],
        }
        path = self._data_dir / "ledger.json"
        path.write_text(json.dumps(data, indent=2))

    def _load(self):
        path = self._data_dir / "ledger.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self.balance = data.get("balance", 0)
            for jid, tc_data in data.get("timecards", {}).items():
                self.timecards[jid] = TimeCard(**tc_data)
            for tx_data in data.get("transactions", []):
                self.transactions.append(CreditTx(
                    job_id=tx_data["job_id"],
                    from_id=tx_data["from_id"],
                    to_id=tx_data["to_id"],
                    amount=tx_data["amount"],
                    timestamp=tx_data["timestamp"],
                ))
            log.info(f"Ledger loaded: balance={self.balance:.2f}, {len(self.transactions)} transactions")
        except Exception as e:
            log.error(f"Failed to load ledger: {e}")
