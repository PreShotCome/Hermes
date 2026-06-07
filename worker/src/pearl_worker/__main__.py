"""Entry point: wire config -> engine -> reporter and start mining."""

from __future__ import annotations

import logging
import sys

from .config import Config
from .engine import LiveEngine, MonitorEngine, ReferenceEngine
from .gateway import MockGatewayClient
from .reporter import Reporter
from .stats import Stats


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("pearl-worker")
    config = Config.parse(argv)
    stats = Stats()

    engine: ReferenceEngine | LiveEngine | MonitorEngine
    if config.mode == "monitor":
        engine = MonitorEngine(
            stats, network=config.network, gateway_endpoint=config.gateway
        )
    elif config.mode == "live":
        engine = LiveEngine(
            stats, network=config.network, gateway_endpoint=config.gateway
        )
    else:
        host, port = config.gateway_host_port()
        gateway = MockGatewayClient(host, port)
        engine = ReferenceEngine(
            gateway,
            stats,
            m=config.matrix_size,
            n=config.matrix_size,
            k=config.common_dim,
            rank=config.rank,
            seed=config.seed,
        )

    info = engine.info
    log.info(
        "starting pearl-worker '%s' | mode=%s device=%s network=%s gateway=%s",
        config.worker_name,
        info.mode,
        info.device,
        info.network,
        config.gateway,
    )
    if info.mode == "reference":
        log.info(
            "REFERENCE MODE: real matmul PoUW, locally verified — earns no PRL. "
            "Use --mode live with a pearld node + GPU to earn."
        )
    elif info.mode == "monitor":
        log.info(
            "MONITOR MODE: reporting GPU power/util/temp and gateway status — "
            "no mining here. The official vllm-miner does the actual mining."
        )

    Reporter(
        config.server_url, config.worker_name, info, stats, config.wallet_address
    ).start()

    try:
        engine.run_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
