"""Process-wide mining counters, shared between the engine and the reporter."""

from __future__ import annotations

import threading
import time


class Stats:
    """Thread-safe counters for one worker process.

    ``matmul_ops`` is the cumulative count of int8 multiply-accumulate operations
    performed — the reporter turns its rate of change into TOPS (tera-ops/sec),
    which is the meaningful throughput measure for Pearl's matmul PoUW (the
    analogue of hashrate for a classic miner).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self.matmul_ops = 0  # cumulative multiply-accumulate operations
        self.solutions = 0  # PoUW solutions found (winning transcripts)
        self.accepted = 0  # solutions accepted by the gateway / chain
        self.rejected = 0  # solutions rejected
        self.gateway_online = False  # is the gateway reachable?
        self.network_difficulty = 0.0  # MAX_TARGET / current target

    def add_matmul_ops(self, n: int) -> None:
        with self._lock:
            self.matmul_ops += n

    def add_solution(self) -> None:
        with self._lock:
            self.solutions += 1

    def add_accepted(self) -> None:
        with self._lock:
            self.accepted += 1

    def add_rejected(self) -> None:
        with self._lock:
            self.rejected += 1

    def set_gateway(self, online: bool, difficulty: float = 0.0) -> None:
        with self._lock:
            self.gateway_online = online
            self.network_difficulty = difficulty

    def gateway_snapshot(self) -> tuple[bool, float]:
        with self._lock:
            return self.gateway_online, self.network_difficulty

    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self._started)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "matmul_ops": self.matmul_ops,
                "solutions": self.solutions,
                "accepted": self.accepted,
                "rejected": self.rejected,
            }
