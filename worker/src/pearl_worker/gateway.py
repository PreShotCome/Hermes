"""Gateway clients — where the worker gets jobs and submits solutions.

The gateway is Pearl's bridge between the miner and the chain. In production it
is ``pearl-gateway`` (newline-terminated JSON-RPC over a Unix socket or TCP). For
zero-config local runs we ship a ``mock-gateway`` that speaks the same protocol,
issuing real Pearl mining jobs (header + target) and validating solutions.

``LiveGatewayClient`` talks to a real ``pearl-gateway`` and matches its wire
format exactly (see upstream ``json_rpc_client.py``: newline-delimited JSON-RPC,
``getMiningInfo`` -> ``{incomplete_header_bytes, target}``), so the worker can
read live jobs / confirm connectivity. Submitting a real block additionally
needs a Plonky2 proof, which only the official ``pearl_mining`` stack produces.
"""

from __future__ import annotations

import base64
import json
import socket
import time
from dataclasses import dataclass
from typing import Protocol

from .pouw import MAX_TARGET, Solution


@dataclass
class GatewayJob:
    """A unit of work: the incomplete block header and the PoW target."""

    header_bytes: bytes
    target: int
    job_id: str = ""

    @property
    def difficulty(self) -> float:
        """Network difficulty implied by the target (MAX_TARGET / target)."""
        return MAX_TARGET / self.target if self.target > 0 else 0.0


class GatewayClient(Protocol):
    network: str
    job_refresh_seconds: float

    def get_job(self) -> GatewayJob: ...

    def submit(self, job: GatewayJob, solution: Solution) -> bool: ...


class _JsonRpcSocketClient:
    """Newline-terminated JSON-RPC over a TCP or Unix-domain socket.

    Matches upstream pearl-gateway framing, so the same client drives both the
    mock gateway (TCP) and a real pearl-gateway (TCP or UDS).
    """

    def __init__(self, endpoint: str, *, timeout: float = 30.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 0

    def _is_uds(self) -> bool:
        return self.endpoint.startswith("/") or self.endpoint.endswith(".sock")

    def _new_socket(self) -> socket.socket:
        if self._is_uds():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect(self.endpoint)
            return s
        host, _, port = self.endpoint.rpartition(":")
        s = socket.create_connection((host or "127.0.0.1", int(port)), timeout=10)
        s.settimeout(self.timeout)
        return s

    def _connect(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        last_err: Exception | None = None
        for delay in (0, 2, 4, 8, 16):
            if delay:
                time.sleep(delay)
            try:
                self._sock = self._new_socket()
                self._buf = b""
                return self._sock
            except OSError as exc:  # pragma: no cover - network timing
                last_err = exc
        raise ConnectionError(f"could not reach gateway at {self.endpoint}: {last_err}")

    def _reset(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        self._buf = b""

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        request["params"] = params if params is not None else {}
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

    @staticmethod
    def _job_from_result(result: dict) -> GatewayJob:
        return GatewayJob(
            header_bytes=base64.b64decode(result["incomplete_header_bytes"]),
            target=int(result["target"]),
            job_id=str(result.get("job_id", "")),
        )


class MockGatewayClient(_JsonRpcSocketClient):
    """Client for the bundled mock gateway (TCP newline JSON-RPC)."""

    network = "mock"

    def __init__(self, host: str, port: int, *, job_refresh_seconds: float = 20.0) -> None:
        super().__init__(f"{host}:{port}")
        self.job_refresh_seconds = job_refresh_seconds

    def get_job(self) -> GatewayJob:
        return self._job_from_result(self.call("getMiningInfo"))

    def submit(self, job: GatewayJob, solution: Solution) -> bool:
        result = self.call(
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


class LiveGatewayClient(_JsonRpcSocketClient):
    """Client for a real pearl-gateway (TCP host:port or a UDS socket path)."""

    def __init__(self, endpoint: str, network: str, *, job_refresh_seconds: float = 10.0) -> None:
        super().__init__(endpoint)
        self.network = network
        self.job_refresh_seconds = job_refresh_seconds

    def get_job(self) -> GatewayJob:
        return self._job_from_result(self.call("getMiningInfo"))

    def submit(self, job: GatewayJob, solution: Solution) -> bool:  # pragma: no cover
        # Real submission requires a Plonky2 proof (submitPlainProof) produced by
        # the official pearl_mining stack — not by the reference engine.
        raise NotImplementedError(
            "submitting to a real gateway needs a ZK proof; use the official "
            "vllm-miner / pearl_mining stack to mine, and this worker in "
            "--mode monitor to watch the rig."
        )
