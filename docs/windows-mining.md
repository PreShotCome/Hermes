# Mining Pearl on Windows (RTX 3060) + this dashboard

A start-to-finish guide for an NVIDIA Windows box: run the node + wallet, run the
real GPU miner, and watch the rig (with power/efficiency) on this dashboard.

> Honest expectations for a 12 GB RTX 3060: use the **8B** model, not the 70B
> (which needs ~140 GB of VRAM). Even 8B is tight on 12 GB — you may need to
> lower `--max-model-len`. A 3060's int8 throughput is modest, so earnings will
> be small and quite possibly below your electricity cost. Treat this as
> learning/experimentation. Only mine on power you pay for.

The helper scripts in [`scripts/windows/`](../scripts/windows/) wrap each step.
Edit the variables at the top of each `.bat` first (paths, RPC user/pass, your
Hugging Face token). Your mining address is already filled in.

## Prerequisites

- The Go binaries you downloaded: `pearld.exe`, `oyster.exe`, `prlctl.exe`
  (e.g. `D:\go-binaries-windows-amd64-v1.0.2`).
- **Docker Desktop** with the WSL2 backend and GPU support enabled
  (Settings → Resources → WSL → enable; install the NVIDIA driver — Docker uses
  it via WSL2). Test: `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi`.
- A free **Hugging Face token** (https://huggingface.co/settings/tokens) for
  downloading the model.
- **Python 3.11+** (for the monitor worker that feeds this dashboard).
- The Pearl repo you cloned (for `docker build` of the miner image).

## Step 1 — Start the node

`scripts/windows/1-start-node.bat`:

```bat
set GOBIN=D:\go-binaries-windows-amd64-v1.0.2
"%GOBIN%\pearld.exe" -u rpcuser -P rpcpass ^
  --txindex --notls ^
  --rpclisten=0.0.0.0:44107 ^
  --miningaddr=prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd
```

`--notls` + `--rpclisten=0.0.0.0` let the Docker miner reach the node over plain
HTTP via `host.docker.internal`. This exposes RPC locally — fine on a trusted
home machine; don't do it on an untrusted network. Let it sync fully first.

## Step 2 — Wallet & mining address

You already gave me your receive address:
`prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd`. That's the
Taproot address rewards pay to — it's wired into the scripts as the
**mining address**. To create/inspect the wallet:

```bat
set GOBIN=D:\go-binaries-windows-amd64-v1.0.2
REM First time only — set a passphrase and SAVE THE SEED:
"%GOBIN%\oyster.exe" -u rpcuser -P rpcpass --create
REM Then run the wallet daemon:
"%GOBIN%\oyster.exe" -u rpcuser -P rpcpass
REM In another window, confirm an address / check balance later:
"%GOBIN%\prlctl.exe" -u rpcuser -P rpcpass -s https://localhost:44207 getnewaddress
"%GOBIN%\prlctl.exe" -u rpcuser -P rpcpass -s https://localhost:44207 getbalance
```

The **key wiring**: the gateway builds the block's coinbase to
`PEARLD_MINING_ADDRESS` (Step 3). That env var = your address. `getbalance` is
how you see earnings land.

## Step 3 — Build & run the GPU miner

The Go binaries are only the node/wallet. The miner (GPU work + `pearl-gateway`
+ ZK proof + block submission) is the Docker image. From the repo root:

```bat
docker build -t vllm_miner . -f miner/vllm-miner/Dockerfile
```

Then `scripts/windows/3-run-miner.bat` (set `HF_TOKEN` first):

```bat
set HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
set MINING_ADDR=prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd

docker run --rm -it --gpus all -p 8000:8000 -p 8337:8337 -p 8339:8339 ^
  -e MINER_NO_GATEWAY=0 ^
  -e PEARLD_RPC_URL=http://host.docker.internal:44107/ ^
  -e PEARLD_RPC_USER=rpcuser -e PEARLD_RPC_PASSWORD=rpcpass ^
  -e PEARLD_MINING_ADDRESS=%MINING_ADDR% ^
  -e MINER_RPC_TRANSPORT=tcp -e MINER_RPC_HOST=0.0.0.0 -e MINER_RPC_PORT=8337 ^
  -e HF_TOKEN=%HF_TOKEN% ^
  -v %USERPROFILE%\.cache\huggingface:/root/.cache/huggingface ^
  --shm-size 8g ^
  vllm_miner:latest ^
  pearl-ai/Llama-3.1-8B-Instruct-pearl ^
  --host 0.0.0.0 --port 8000 --max-model-len 4096 --gpu-memory-utilization 0.9 --enforce-eager
```

If it OOMs on the 3060, lower `--max-model-len` (2048) and/or
`--gpu-memory-utilization` (0.85). `MINER_RPC_TRANSPORT=tcp` exposes the gateway
on port 8337 so the monitor worker (Step 5) can reach it.

## Step 4 — Run the dashboard

From the repo root (just the server + dashboard, no mock/worker):

```bat
docker compose up -d server dashboard
```

Open http://localhost:8080.

## Step 5 — Put the rig on the dashboard

Install and run the monitor worker (reports GPU power/util/temp + gateway status,
does no mining of its own). `scripts/windows/5-run-monitor.bat`:

```bat
pip install -e worker
pearl-worker --mode monitor --network mainnet ^
  --gateway 127.0.0.1:8337 ^
  --worker-name rtx3060-rig ^
  --wallet-address prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd ^
  --server-url http://127.0.0.1:4000
```

The card shows live **power draw and TOPS/W** for the 3060, plus whether the
gateway is online and the current network difficulty. Watch `prlctl ...
getbalance` for actual rewards.

## Power efficiency on the 3060

To cut electricity cost while keeping most throughput, cap board power (run as
admin):

```bat
nvidia-smi -pl 130
```

The 3060's stock limit is ~170 W; ~120–140 W usually keeps most of the
throughput at much better TOPS/W. Compare efficiency on the dashboard before/after.
```
