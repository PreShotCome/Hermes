import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';

/** Open (creating if needed) the SQLite database and ensure the schema. */
export function openDatabase(dbPath: string): Database.Database {
  if (dbPath !== ':memory:') {
    fs.mkdirSync(path.dirname(path.resolve(dbPath)), { recursive: true });
  }
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS workers (
      id             TEXT PRIMARY KEY,
      name           TEXT NOT NULL,
      host           TEXT NOT NULL,
      device         TEXT NOT NULL DEFAULT '',
      mode           TEXT NOT NULL DEFAULT 'reference',
      network        TEXT NOT NULL DEFAULT '',
      wallet         TEXT NOT NULL DEFAULT '',
      created_at     INTEGER NOT NULL,
      last_seen      INTEGER NOT NULL,
      status         TEXT NOT NULL,
      tops           REAL NOT NULL DEFAULT 0,
      solutions      INTEGER NOT NULL DEFAULT 0,
      accepted       INTEGER NOT NULL DEFAULT 0,
      rejected       INTEGER NOT NULL DEFAULT 0,
      uptime_seconds INTEGER NOT NULL DEFAULT 0,
      power_watts    REAL NOT NULL DEFAULT 0,
      gpu_util       REAL NOT NULL DEFAULT 0,
      gpu_temp       REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS samples (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      worker_id      TEXT NOT NULL,
      ts             INTEGER NOT NULL,
      tops           REAL NOT NULL,
      solutions      INTEGER NOT NULL,
      accepted       INTEGER NOT NULL,
      rejected       INTEGER NOT NULL,
      uptime_seconds INTEGER NOT NULL,
      power_watts    REAL NOT NULL DEFAULT 0,
      gpu_util       REAL NOT NULL DEFAULT 0,
      gpu_temp       REAL NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_samples_worker_ts ON samples (worker_id, ts);
  `);
  return db;
}
