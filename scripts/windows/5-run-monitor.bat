@echo off
REM Put the real 3060 rig on the dashboard: report GPU power/util/temp + gateway
REM status. Does NOT mine (the vLLM container does that). Needs Python 3.11+.
setlocal
set MINING_ADDR=prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd

REM Install the worker once (run from repo root). Comment out after first run.
pip install -e worker

pearl-worker --mode monitor --network mainnet ^
  --gateway 127.0.0.1:8337 ^
  --worker-name rtx3060-rig ^
  --wallet-address %MINING_ADDR% ^
  --server-url http://127.0.0.1:4000
endlocal
