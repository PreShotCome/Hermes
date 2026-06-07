"""Worker configuration from CLI flags (each backed by an environment variable)."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Config:
    mode: str  # "reference" | "live"
    gateway: str  # host:port (mock) or socket/host of pearl-gateway (live)
    network: str  # label: mock | mainnet | testnet | ...
    wallet_address: str  # mining payout address (live mode)
    worker_name: str
    server_url: str  # monitoring server base URL ("" disables reporting)
    matrix_size: int  # m == n for the reference engine's square problem
    common_dim: int  # k
    rank: int  # low-rank noise rank
    seed: int | None  # RNG seed for reproducible reference runs

    @staticmethod
    def parse(argv: list[str] | None = None) -> "Config":
        p = argparse.ArgumentParser(
            prog="pearl-worker",
            description="Pearl Proof-of-Useful-Work miner (matmul) with dashboard reporting",
        )
        p.add_argument(
            "--mode",
            default=_env("MINER_MODE", "reference"),
            choices=["reference", "live", "monitor"],
            help="reference = real CPU matmul PoUW, earns nothing (default); "
            "live = submit ZK proofs to a real pearld node and earn PRL; "
            "monitor = watch a real rig (GPU power + gateway status), no mining",
        )
        p.add_argument(
            "--gateway",
            default=_env("GATEWAY", "127.0.0.1:3434"),
            help="mock gateway host:port, or pearl-gateway endpoint (host:port "
            "or UDS socket path) in live/monitor mode",
        )
        p.add_argument("--network", default=_env("NETWORK", "mock"))
        p.add_argument(
            "--wallet-address",
            default=_env("WALLET_ADDRESS", ""),
            help="Taproot mining address rewards pay to (live mode)",
        )
        p.add_argument("--worker-name", default=_env("WORKER_NAME", "pearl-worker-1"))
        p.add_argument(
            "--server-url",
            default=_env("SERVER_URL", "http://127.0.0.1:4000"),
            help="monitoring server base URL; set empty to disable reporting",
        )
        p.add_argument("--matrix-size", type=int, default=int(_env("MATRIX_SIZE", "256")))
        p.add_argument("--common-dim", type=int, default=int(_env("COMMON_DIM", "256")))
        p.add_argument("--rank", type=int, default=int(_env("RANK", "128")))
        seed_env = os.environ.get("SEED")
        p.add_argument("--seed", type=int, default=int(seed_env) if seed_env else None)
        args = p.parse_args(argv)

        return Config(
            mode=args.mode,
            gateway=args.gateway,
            network=args.network,
            wallet_address=args.wallet_address,
            worker_name=args.worker_name,
            server_url=args.server_url.strip(),
            matrix_size=args.matrix_size,
            common_dim=args.common_dim,
            rank=args.rank,
            seed=args.seed,
        )

    def gateway_host_port(self) -> tuple[str, int]:
        host, _, port = self.gateway.rpartition(":")
        return host or "127.0.0.1", int(port)
