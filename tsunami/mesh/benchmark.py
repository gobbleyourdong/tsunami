"""Capability benchmark — quick self-assessment of node hardware.

Runs in <2 seconds. Produces a single score used for:
- Job matching (don't send GPU jobs to a Raspberry Pi)
- Credit calculation (faster machine = more credits per second)
- Handshake verification (claimed capability vs actual performance)
"""

import hashlib
import logging
import time

log = logging.getLogger("megalan.benchmark")


def _bench_cpu() -> float:
    """SHA-256 hash 1MB of data. Returns hashes/second."""
    data = b"megalan_benchmark" * (1024 * 1024 // 17)
    t0 = time.monotonic()
    count = 0
    while time.monotonic() - t0 < 0.5:
        hashlib.sha256(data).digest()
        count += 1
    elapsed = time.monotonic() - t0
    return count / elapsed


def _bench_memory() -> float:
    """Allocate and fill 100MB. Returns MB/second throughput."""
    size = 100 * 1024 * 1024
    t0 = time.monotonic()
    try:
        buf = bytearray(size)
        for i in range(0, size, 4096):
            buf[i] = 0xFF
        elapsed = time.monotonic() - t0
        return 100 / elapsed if elapsed > 0 else 0
    except MemoryError:
        return 0


def _bench_gpu() -> float:
    """Quick matrix multiply if torch + CUDA available. Returns GFLOPS."""
    try:
        import torch
        if not torch.cuda.is_available():
            return 0
        n = 1024
        a = torch.randn(n, n, device="cuda")
        b = torch.randn(n, n, device="cuda")
        torch.cuda.synchronize()
        t0 = time.monotonic()
        for _ in range(10):
            torch.mm(a, b)
        torch.cuda.synchronize()
        elapsed = time.monotonic() - t0
        flops = 10 * 2 * n * n * n  # 2N^3 per matmul
        return flops / elapsed / 1e9  # GFLOPS
    except ImportError:
        return 0
    except Exception:
        return 0


def run_benchmark() -> float:
    """Run all benchmarks and return a combined capability score.

    Scale:
      Raspberry Pi:     5-10
      Old laptop:       15-30
      Modern laptop:    40-60
      Gaming desktop:   80-120
      GPU workstation:  150+
    """
    cpu_score = _bench_cpu()
    mem_score = _bench_memory()
    gpu_score = _bench_gpu()

    # Normalize to rough 0-200 scale
    # CPU: ~50 hashes/s on modern laptop → score ~50
    cpu_normalized = min(cpu_score, 100)
    # Memory: ~5000 MB/s on modern laptop → score ~50
    mem_normalized = min(mem_score / 100, 50)
    # GPU: ~5 TFLOPS on RTX 3060 → score ~100
    gpu_normalized = min(gpu_score / 50, 100)

    total = cpu_normalized * 1.0 + mem_normalized * 0.5 + gpu_normalized * 2.0

    log.info(f"Benchmark: CPU={cpu_score:.1f} h/s, MEM={mem_score:.0f} MB/s, "
             f"GPU={gpu_score:.1f} GFLOPS → score={total:.1f}")

    return round(total, 1)
