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

## Efficiency

Energy-per-solution is what matters for PoUW. The reference engine is tuned to
waste as little CPU (and therefore power) as possible — it is ~12x faster per
attempt than a naive implementation:

- **BLAS integer matmul.** numpy has no optimized integer-matmul kernel, so it
  falls back to a slow generic loop. `pouw._imatmul` routes through float32 (or
  float64 when needed) BLAS — *bit-exact* for these int8 inputs — for a ~30x
  matmul speedup.
- **Vectorized transcript search.** The per-hash-tile XOR inner hash and the
  rotl-xor transcript accumulation run as single numpy passes over the whole
  output, not Python loops; noise permutation generation is vectorized too.
- **No redundant work in the hot loop.** The denoised product and the `A @ B`
  self-check are computed once at startup, not on every attempt (they cost ~3
  extra matmuls each).

Tuning knobs:

- `RANK` / `MATRIX_SIZE` / `COMMON_DIM` trade per-attempt overhead against work
  per attempt; larger problems amortize fixed costs over more transcript checks.
- Ensure numpy is linked against a fast BLAS (OpenBLAS/MKL) — `python -c "import
  numpy; numpy.show_config()"`.

For **live GPU mining**, power efficiency (TOPS/watt, joules/solution) is
dominated by the GPU, not this worker:

- Cap the board power and/or undervolt (`nvidia-smi -pl <watts>`); the efficiency
  sweet spot is usually well below stock — you keep most of the throughput for a
  fraction of the watts.
- Watch joules-per-accepted-block, not raw throughput.
- Mine when electricity is cheapest, and only on power you pay for or are
  authorized to use.

## Tests

```bash
pip install -e '.[test]'
pytest
```
