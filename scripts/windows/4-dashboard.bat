@echo off
REM Start the monitoring server + dashboard (no mock gateway, no CPU worker).
REM Run from the repo root. Open http://localhost:8080 afterwards.
docker compose up -d server dashboard
echo Dashboard: http://localhost:8080
echo Server:    http://localhost:4000/health
