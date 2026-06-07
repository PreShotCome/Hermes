# pearl-worker

A Pearl Proof-of-Useful-Work miner. Pearl secures its chain with *useful* work:
a miner runs a large int8 matrix multiplication (the same GEMM that powers AI
inference), accumulates a keyed-BLAKE3 transcript over the output tiles, and
wins a block when a tile's transcript hash falls below the network target. This
worker implements that, and reports live stats to the monitoring server.

It has two modes.

## Reference mode (default) — real work, runs anywhere, earns nothing

```bash
pip install -e .
pearl-worker --gateway 127.0.0.1:3434 --server-url http://127.0.0.1:4000
```

Reference mode runs the genuine Pearl noisy-GEMM PoUW in pure `numpy` + `blake3`
(`pearl_worker/pouw.py`) on the CPU — no GPU, no CUDA, no compiled extension. It
finds and **locally verifies** real solutions against jobs from a gateway (the
bundled `mock-gateway` by default). It does **not** wrap solutions in Plonky2 ZK
proofs or submit them to a real chain, so it earns no PRL. Use it for
development, testing, benchmarking and the zero-config demo.

Key flags (all also settable via the matching environment variable):

| Flag / env | Default | Description |
|---|---|---|
| `--mode` / `MINER_MODE` | `reference` | `reference` or `live` |
| `--gateway` / `GATEWAY` | `127.0.0.1:3434` | mock gateway `host:port`, or pearl-gateway endpoint (live) |
| `--network` / `NETWORK` | `mock` | label shown on the dashboard |
| `--worker-name` / `WORKER_NAME` | `pearl-worker-1` | name shown on the dashboard |
| `--server-url` / `SERVER_URL` | `http://127.0.0.1:4000` | monitoring server (empty = off) |
| `--matrix-size` / `MATRIX_SIZE` | `256` | reference engine square problem size (m == n) |
| `--common-dim` / `COMMON_DIM` | `256` | k dimension |
| `--rank` / `RANK` | `128` | low-rank noise rank |
| `--wallet-address` / `WALLET_ADDRESS` | `` | payout address (live mode) |

## Live mode — submit to a real node and earn PRL

```bash
pearl-worker --mode live \
  --gateway /tmp/pearlgw.sock \
  --network mainnet \
  --wallet-address <your-taproot-address> \
  --server-url http://127.0.0.1:4000
```

Live mode is the money path. It delegates the heavy lifting to the **official
Pearl stack** (`pearl_mining` bindings + `pearl-gateway`), which performs the GPU
GEMM, wraps the solution in a Plonky2 ZK proof, and submits the block to a synced
`pearld` node — paying the reward to your wallet.

It requires that stack to be installed and running:

1. **Build the Pearl mining bindings** from
   [github.com/pearl-research-labs/pearl](https://github.com/pearl-research-labs/pearl):
   `cd py-pearl-mining && maturin develop --release` (needs a Rust toolchain).
2. **Run a synced `pearld` node** with `--miningaddr=<your address>`.
3. **Create a wallet** with `oyster` and a Taproot address with `prlctl getnewaddress`.
4. **Run `pearl-gateway`** pointed at the node; it exposes a mining socket
   (`/tmp/pearlgw.sock` or TCP `:8337`).
5. Realistically, a **CUDA GPU** running the `vllm-miner` — the CPU `mine()` path
   exists but is far too slow to be competitive on mainnet.

Point `--gateway` at the gateway's socket/host. This worker drives the gateway's
`getMiningInfo` / `submitPlainProof` loop and mirrors its counters to the
dashboard. Block rewards accrue to the `--miningaddr` configured on `pearld`.

> Honest note: Pearl mining profitability is thin and declining, and you only
> profit when reward value exceeds your electricity cost. Mine only on power you
> pay for or are authorized to use.

## Tests

```bash
pip install -e '.[test]'
pytest
```
