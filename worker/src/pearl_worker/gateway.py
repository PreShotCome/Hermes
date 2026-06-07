"""Gateway clients — where the worker gets jobs and submits solutions.

The gateway is Pearl's bridge between the miner and the chain. In production it
is ``pearl-gateway`` (talking JSON-RPC to a ``pearld`` node over a Unix socket or
TCP). For zero-config local runs we ship a ``mock-gateway`` that speaks the same
shape of protocol — newline-delimited JSON-RPC over TCP — issuing real Pearl
mining jobs (header + target) and validating submitted solutions.
"""

from __future__ import annotations

import base64
import json
import socket
import time
from dataclasses import dataclass
from typing import Protocol

from .pouw import Solution


@dataclass
class GatewayJob:
    """A unit of work: the incomplete block header and the PoW target."""

    header_bytes: bytes
    target: int
    job_id: str = ""


class GatewayClient(Protocol):
    network: str
    job_refresh_seconds: float

    def get_job(self) -> GatewayJob: ...

    def submit(self, job: GatewayJob, solution: Solution) -> bool: ...


class MockGatewayClient:
    """Client for the bundled mock gateway (newline JSON-RPC over TCP)."""

    network = "mock"

    def __init__(self, host: str, port: int, *, job_refresh_seconds: float = 20.0) -> None:
        self.host = host
        self.port = port
        self.job_refresh_seconds = job_refresh_seconds
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 0

    # -- connection management (reconnects transparently on failure) ----------

    def _connect(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        last_err: Exception | None = None
        for delay in (0, 2, 4, 8, 16):
            if delay:
                time.sleep(delay)
            try:
                s = socket.create_connection((self.host, self.port), timeout=10)
                s.settimeout(30)
                self._sock = s
                self._buf = b""
                return s
            except OSError as exc:  # pragma: no cover - network timing
                last_err = exc
        raise ConnectionError(
            f"could not reach mock gateway at {self.host}:{self.port}: {last_err}"
        )

    def _reset(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        self._buf = b""

    def _call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            request["params"] = params
        sock = self._connect()
        try:
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
            while b"\n" not in self._buf:
                chunk = sock.recv(65536)
                if not chunk:
                    raise ConnectionError("gateway closed the connection")
                self._buf += chunk
        except OSError:
            self._reset()
            raise
        line, self._buf = self._buf.split(b"\n", 1)
        message = json.loads(line.decode("utf-8"))
        if message.get("error"):
            raise RuntimeError(f"gateway error: {message['error']}")
        return message.get("result", {})

    # -- protocol -------------------------------------------------------------

    def get_job(self) -> GatewayJob:
        result = self._call("getMiningInfo")
        return GatewayJob(
            header_bytes=base64.b64decode(result["incomplete_header_bytes"]),
            target=int(result["target"]),
            job_id=str(result.get("job_id", "")),
        )

    def submit(self, job: GatewayJob, solution: Solution) -> bool:
        result = self._call(
            "submitSolution",
            {
                "job_id": job.job_id,
                "row": solution.row,
                "col": solution.col,
                "transcript": solution.transcript,
                "pow_hash": format(solution.pow_hash_int, "064x"),
            },
        )
        return bool(result.get("accepted", False))
