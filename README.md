# Pearl Mining App

A [Pearl](https://pearlresearch.ai/) Proof-of-Useful-Work miner plus a live
monitoring dashboard, in one monorepo. A worker performs Pearl's matmul PoUW,
reports its stats to a server, and a web dashboard shows every worker in one
view.

```
worker (Python) ──mines──▶ gateway (real pearl-gateway, or bundled mock)
      │
      └──heartbeats──▶ server (Node/TS, REST + WebSocket + SQLite)
                              │
                              └──live feed──▶ dashboard (React PWA)
```

Built on the proven worker → server → dashboard → mock shape, adapted from the
DwarfSimulator mining framework to Pearl's GPU/matmul PoUW.

## Read this first — honest expectations

- **Pearl is Proof-of-*Useful*-Work.** Instead of hashing nonces, a miner runs a
  large int8 matrix multiplication (the core op of AI inference), accumulates a
  keyed-BLAKE3 transcript over the output tiles, and wins a block when a tile's
  transcript hash falls below the target. See the
  [paper](https://arxiv.org/abs/2504.09971) and
  [github.com/pearl-research-labs/pearl](https://github.com/pearl-research-labs/pearl).
- **Earning PRL requires real hardware you control.** A synced `pearld` node, a
  wallet/mining address, `pearl-gateway`, and realistically a CUDA GPU. The
  worker's **live** mode drives that stack; see [Live mining](#live-mining).
- **Reference mode earns nothing — by design.** It does *real, locally-verified*
  Pearl matmul work on any CPU so you can run, test and demo the whole system
  with zero setup, but it does not submit ZK proofs to a chain.
- **Profitability is thin and declining.** You only profit when reward value
  exceeds your electricity cost. **Only mine on power you pay for or are
  explicitly authorized to use.**

## Repository layout

| Path | Stack | Purpose |
|------|-------|---------|
| `worker/` | Python | Pearl matmul PoUW miner (reference CPU engine + live adapter) |
| `server/` | Node / TypeScript | Aggregates worker stats; REST + WebSocket; SQLite |
| `dashboard/` | React + Vite | Installable PWA showing all workers live |
| `mock-gateway/` | Node / TypeScript | Minimal mock Pearl gateway for zero-config local runs |

## Quick start (Docker — recommended)

Requires Docker with Compose.

```bash
docker compose up --build
```

This starts the mock gateway, the server, the dashboard, and one reference
worker mining against the mock gateway. Then open:

- **Dashboard:** http://localhost:8080
- **Server API:** http://localhost:4000/health

You should see `docker-worker-1` appear within a few seconds, its throughput
(TOPS) climb above zero, and solutions accumulate.

Stop with `Ctrl+C`; `docker compose down` removes the containers. Stats history
is kept in the `monitor-data` volume.

## Quick start (native)

Prerequisites: Node.js 20+, Python 3.11+.

In separate terminals:

```bash
# 1. Install JS dependencies (once)
npm run install:all

# 2. Mock gateway + server + dashboard together
npm run dev

# 3. The worker (Python)
cd worker
pip install -e .
pearl-worker
```

Defaults make the worker connect to the local mock gateway (`127.0.0.1:3434`)
and report to the local server (`http://127.0.0.1:4000`). The dashboard dev
server runs at http://localhost:5173.

## Running multiple workers

Each worker is an independent process — run as many as you like, on one machine
or across several devices, and they all appear on the dashboard. Give each a
unique name:

```bash
WORKER_NAME=living-room-pc pearl-worker
WORKER_NAME=laptop SERVER_URL=http://192.168.1.10:4000 pearl-worker
```

Point `SERVER_URL` at the machine running the server when mining from other
devices. With Docker, scale the worker service:

```bash
docker compose up --build --scale worker=3
```

## Live mining

CPU/reference mode never earns. To mine real PRL, run a worker in `live` mode
against the official Pearl stack on hardware you control:

1. **Run a synced `pearld` node** with `--miningaddr=<your-taproot-address>`
   (create the wallet/address with `oyster` + `prlctl getnewaddress`).
2. **Build `pearl_mining`** (`maturin develop --release`) and **run
   `pearl-gateway`** pointed at the node — it exposes a mining socket
   (`/tmp/pearlgw.sock` or TCP `:8337`).
3. Run a GPU miner (`vllm-miner`) for competitive throughput.
4. Start a live worker so it shows up on this dashboard:

   ```bash
   pearl-worker --mode live --network mainnet \
     --gateway /tmp/pearlgw.sock \
     --wallet-address <your-taproot-address> \
     --server-url http://127.0.0.1:4000
   ```

Block rewards accrue to the mining address configured on `pearld`. See
[`worker/README.md`](worker/README.md) for full details.

## Worker configuration

See the table in [`worker/README.md`](worker/README.md). All flags are also
settable via environment variables (e.g. `MINER_MODE`, `GATEWAY`, `NETWORK`,
`WORKER_NAME`, `SERVER_URL`, `WALLET_ADDRESS`).

## Server configuration

| Env | Default | Description |
|-----|---------|-------------|
| `PORT` | `4000` | HTTP + WebSocket port |
| `DB_PATH` | `./data/monitor.db` | SQLite database path |
| `HEARTBEAT_TIMEOUT_MS` | `20000` | Silence before a worker goes offline |
| `HISTORY_RETENTION_MS` | `86400000` | How long stats history is kept |

### Server API

- `GET  /health`
- `GET  /api/workers` · `GET /api/workers/:id`
- `GET  /api/workers/:id/history?minutes=60`
- `GET  /api/stats/summary`
- `POST /api/workers/register` · `POST /api/workers/:id/heartbeat`
- `WS   /ws` — pushes a full fleet snapshot on connect and on every change

## Install the dashboard as an app

The dashboard is a PWA. Open it in a browser and use **Install app** (desktop
Chrome/Edge) or **Add to Home Screen** (mobile).

## Tests

```bash
cd worker && pip install -e '.[test]' && pytest   # PoUW correctness + solution search
npm --prefix server test                          # store, aggregation, stale detection
```

## How the worker works (reference mode)

1. Fetches a job from the gateway (`getMiningInfo` → incomplete block header + target).
2. Draws int8 input matrices A, B and derives the commitment seeds binding them
   to the header (so noise can't be ground for free).
3. Generates low-rank int8 noise, runs the tiled noisy GEMM, and accumulates a
   keyed-BLAKE3 transcript per output hash tile.
4. A tile whose `BLAKE3(transcript, key) <= target` is a solution; it is
   verified locally (the denoised product equals A·B) and submitted to the gateway.
5. Every 5 seconds it posts a heartbeat (TOPS, solutions, accepted, rejected,
   uptime, plus GPU power/util/temp via `nvidia-smi` when available) to the
   monitoring server. The dashboard shows fleet power and **efficiency
   (TOPS/W)** — the number to maximize to save on electricity.

In **live** mode steps 2–4 are performed by the official `pearl_mining` /
`pearl-gateway` stack (GPU GEMM + Plonky2 ZK proof + block submission).
