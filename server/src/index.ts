import http from 'node:http';
import express from 'express';
import { config } from './config';
import { Store } from './store';
import { createApiRouter } from './api';
import { attachWebSocket } from './ws';

const store = new Store(config.dbPath, config.heartbeatTimeoutMs);

const app = express();
app.use(express.json());

// Permissive CORS so the dashboard can be served from a different origin.
app.use((_req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  next();
});
app.options(/.*/, (_req, res) => res.sendStatus(204));

app.use('/api', createApiRouter(store));
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

const server = http.createServer(app);
attachWebSocket(server, store);

// Periodically flag workers that stopped sending heartbeats.
const staleTimer = setInterval(() => store.markStale(), 5_000);
// Periodically drop history beyond the retention window.
const pruneTimer = setInterval(
  () => store.pruneHistory(config.historyRetentionMs),
  60 * 60 * 1000,
);

server.listen(config.port, () => {
  console.log(`pearl-monitor-server listening on http://0.0.0.0:${config.port}`);
});

function shutdown(): void {
  clearInterval(staleTimer);
  clearInterval(pruneTimer);
  server.close(() => {
    store.close();
    process.exit(0);
  });
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
