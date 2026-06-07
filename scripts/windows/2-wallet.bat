@echo off
REM Create (first run) and start the Oyster wallet, then show balance.
setlocal
set GOBIN=D:\go-binaries-windows-amd64-v1.0.2

if /I "%1"=="create" (
  echo Creating wallet. Set a passphrase and SAVE THE SEED PHRASE.
  "%GOBIN%\oyster.exe" -u rpcuser -P rpcpass --create
  goto :eof
)
if /I "%1"=="balance" (
  "%GOBIN%\prlctl.exe" -u rpcuser -P rpcpass -s https://localhost:44207 getbalance
  goto :eof
)
if /I "%1"=="address" (
  "%GOBIN%\prlctl.exe" -u rpcuser -P rpcpass -s https://localhost:44207 getnewaddress
  goto :eof
)

REM Default: run the wallet daemon (leave this window open).
echo Usage: 2-wallet.bat [create^|balance^|address]   (no arg = run wallet daemon)
"%GOBIN%\oyster.exe" -u rpcuser -P rpcpass
endlocal
