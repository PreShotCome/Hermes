"""Mining engines: a pure-numpy reference engine and a live ``pearl_mining`` one.

``ReferenceEngine`` runs the real Pearl PoUW computation (``pouw``) on the CPU
against jobs from a gateway (the bundled mock gateway by default). It does
genuine matmul work and finds genuine, self-verifiable solutions — but it does
not produce ZK proofs or submit to a real chain, so it earns nothing. It is for
development, testing, benchmarking and the zero-config demo.

``LiveEngine`` is the money path. It delegates to the official ``pearl_mining``
bindings + ``pearl-gateway`` so solutions are wrapped in Plonky2 proofs and
submitted to a real ``pearld`` node, paying block rewards to your wallet. It
requires that production stack (and realistically a CUDA GPU) to be installed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from . import pouw
from .gateway import GatewayJob, GatewayClient
from .stats import Stats


@dataclass
class EngineInfo:
    mode: str  # "reference" | "live"
    device: str  # human label, e.g. "cpu (numpy)" or "NVIDIA RTX 4090"
    network: str  # "mock" | "mainnet" | "testnet" | ...


class ReferenceEngine:
    """CPU noisy-GEMM PoUW miner. Real work, locally verified, earns nothing."""

    def __init__(
        self,
        gateway: GatewayClient,
        stats: Stats,
        *,
        m: int = 256,
        n: int = 256,
        k: int = 256,
        rank: int = 128,
        seed: int | None = None,
    ) -> None:
        self.gateway = gateway
        self.stats = stats
        self.m, self.n, self.k, self.rank = m, n, k, rank
        self.cfg = pouw.MiningConfig(common_dim=k, rank=rank)
        self.noise_gen = pouw.NoiseGenerator(noise_rank=rank)
        self.rng = np.random.default_rng(seed)

    @property
    def info(self) -> EngineInfo:
        return EngineInfo(mode="reference", device="cpu (numpy)", network=self.gateway.network)

    def _random_data(self) -> tuple[np.ndarray, np.ndarray]:
        # int8 data in the valid range [-64, 63] (256 - NOISE_RANGE == 128 wide).
        lo, hi = -64, 64
        a = self.rng.integers(lo, hi, size=(self.m, self.k), dtype=np.int8)
        b = self.rng.integers(lo, hi, size=(self.k, self.n), dtype=np.int8)
        return a, b

    def _attempt(self, job: GatewayJob) -> pouw.Solution | None:
        a, b = self._random_data()
        seed_a, seed_b = pouw.commitment(a, b, job.header_bytes, self.cfg)
        noise = self.noise_gen.generate(seed_a, seed_b, self.m, self.k, self.n)
        c, solution = pouw.noisy_gemm_pow(a, b, noise, seed_a, job.target, self.cfg)
        # Correctness check: the noised computation must reproduce the plain matmul.
        if not np.array_equal(c, a.astype(np.int32) @ b.astype(np.int32)):
            raise RuntimeError("noisy GEMM did not reproduce A @ B — engine bug")
        self.stats.add_matmul_ops(pouw.matmul_ops(self.m, self.n, self.k))
        return solution

    def run_forever(self) -> None:
        job = self.gateway.get_job()
        last_job_poll = time.monotonic()
        while True:
            solution = self._attempt(job)
            if solution is not None:
                self.stats.add_solution()
                accepted = self.gateway.submit(job, solution)
                if accepted:
                    self.stats.add_accepted()
                else:
                    self.stats.add_rejected()
            # Refresh the job periodically (new block template / target).
            if time.monotonic() - last_job_poll > self.gateway.job_refresh_seconds:
                job = self.gateway.get_job()
                last_job_poll = time.monotonic()


class LiveEngine:
    """Real network miner via the official ``pearl_mining`` + ``pearl-gateway``.

    This is intentionally a thin adapter: the heavy lifting (GPU GEMM kernels,
    Plonky2 proving, block submission) lives in the upstream Pearl stack. We only
    import it, drive its mining loop, and mirror its counters onto the dashboard.
    """

    def __init__(self, stats: Stats, *, network: str, gateway_endpoint: str) -> None:
        self.stats = stats
        self.network = network
        self.gateway_endpoint = gateway_endpoint
        try:  # imported lazily so reference mode never needs the GPU stack.
            import pearl_mining  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on host install
            raise RuntimeError(
                "live mode requires the official Pearl mining stack.\n"
                "Install it from github.com/pearl-research-labs/pearl:\n"
                "  - build py-pearl-mining (maturin develop --release)\n"
                "  - run a synced pearld node and pearl-gateway\n"
                "  - point --gateway at the gateway socket/host\n"
                "See the worker README 'Live mining' section."
            ) from exc

    @property
    def info(self) -> EngineInfo:
        return EngineInfo(mode="live", device=_detect_gpu(), network=self.network)

    def run_forever(self) -> None:  # pragma: no cover - requires GPU + node
        raise NotImplementedError(
            "Live mining drives the upstream pearl-gateway mining loop. Wire this "
            "to pearl_gateway.MiningClient.get_mining_info()/submit_plain_proof() "
            "on your GPU rig; see worker/README.md."
        )


def _detect_gpu() -> str:  # pragma: no cover - host dependent
    try:
        import subprocess

        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            timeout=3,
        )
        name = out.strip().splitlines()[0].strip()
        return name or "gpu"
    except Exception:
        return "gpu (unknown)"
