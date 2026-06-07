@echo off
REM Build (first time) and run the real GPU miner (pearl-gateway + vLLM).
REM Set HF_TOKEN below to your Hugging Face token before running.
setlocal
set HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
set MINING_ADDR=prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd
set MODEL=pearl-ai/Llama-3.1-8B-Instruct-pearl

REM Build once (run from the cloned pearl repo root). Comment out after first build.
docker build -t vllm_miner . -f miner/vllm-miner/Dockerfile

REM 12 GB RTX 3060: if this OOMs, lower --max-model-len (2048) and/or
REM --gpu-memory-utilization (0.85).
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
  %MODEL% ^
  --host 0.0.0.0 --port 8000 --max-model-len 4096 --gpu-memory-utilization 0.9 --enforce-eager
endlocal
