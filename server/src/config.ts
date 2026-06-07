/** Server configuration, sourced from environment variables. */
export const config = {
  port: Number(process.env.PORT ?? 4000),
  dbPath: process.env.DB_PATH ?? './data/monitor.db',
  /** A worker with no heartbeat within this window is considered offline. */
  heartbeatTimeoutMs: Number(process.env.HEARTBEAT_TIMEOUT_MS ?? 20_000),
  /** Historical samples older than this are pruned. */
  historyRetentionMs: Number(process.env.HISTORY_RETENTION_MS ?? 24 * 60 * 60 * 1000),
};
