@echo off
REM Start the Pearl full node (pearld). Edit GOBIN to where your binaries live.
setlocal
set GOBIN=D:\go-binaries-windows-amd64-v1.0.2
set MINING_ADDR=prl1p5ywq9mcrypuveyd8at8n8yd0ulfkdrqsseaql504zasq3arwdxnqrtxumd

REM --notls + rpclisten 0.0.0.0 let the Docker miner reach the node via
REM host.docker.internal. Trusted home machine only.
"%GOBIN%\pearld.exe" -u rpcuser -P rpcpass ^
  --txindex --notls ^
  --rpclisten=0.0.0.0:44107 ^
  --miningaddr=%MINING_ADDR%
endlocal
