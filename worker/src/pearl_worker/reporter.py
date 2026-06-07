"""Register with the monitoring server and push heartbeats on a fixed cadence.

Reporting failures are logged and retried; they never interrupt mining. Runs in
a daemon thread so the engine owns the main thread.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request

from .engine import EngineInfo
from .power import sample_gpu
from .stats import Stats

_LOG = logging.getLogger("pearl-worker.reporter")
HEARTBEAT_INTERVAL = 5.0


def _post(url: str, body: dict, timeout: float = 10.0) -> dict | None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _LOG.warning("POST %s failed: %s", url, exc)
        return None


class Reporter(threading.Thread):
    def __init__(
        self,
        server_url: str,
        worker_name: str,
        info: EngineInfo,
        stats: Stats,
        wallet_address: str = "",
    ) -> None:
        super().__init__(daemon=True)
        self.base = server_url.rstrip("/")
        self.worker_name = worker_name
        self.info = info
        self.stats = stats
        self.wallet_address = wallet_address
        self._worker_id: str | None = None

    def _register(self) -> None:
        body = {
            "name": self.worker_name,
            "host": socket.gethostname(),
            "device": self.info.device,
            "mode": self.info.mode,
            "network": self.info.network,
            "wallet": self.wallet_address,
        }
        while self._worker_id is None:
            result = _post(f"{self.base}/api/workers/register", body)
            if result and "id" in result:
                self._worker_id = result["id"]
                _LOG.info("registered with monitoring server as %s", self._worker_id)
                return
            time.sleep(HEARTBEAT_INTERVAL)

    def run(self) -> None:
        if not self.base:
            _LOG.info("monitoring disabled (no server URL)")
            return
        self._register()
        prev_ops = self.stats.snapshot()["matmul_ops"]
        prev = time.monotonic()
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            now = time.monotonic()
            snap = self.stats.snapshot()
            dt = max(now - prev, 1e-3)
            tops = (snap["matmul_ops"] - prev_ops) / dt / 1e12
            prev_ops = snap["matmul_ops"]
            prev = now
            body = {
                "tops": tops,
                "solutions": snap["solutions"],
                "accepted": snap["accepted"],
                "rejected": snap["rejected"],
                "uptimeSeconds": self.stats.uptime_seconds(),
            }
            power = sample_gpu()
            if power is not None:
                body["powerWatts"] = power.power_watts
                body["gpuUtil"] = power.gpu_util
                body["gpuTemp"] = power.gpu_temp
            online, difficulty = self.stats.gateway_snapshot()
            body["gatewayOnline"] = online
            body["networkDifficulty"] = difficulty
            _post(f"{self.base}/api/workers/{self._worker_id}/heartbeat", body)
