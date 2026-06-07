import { EventEmitter } from 'node:events';
import { randomUUID } from 'node:crypto';
import type Database from 'better-sqlite3';
import { openDatabase } from './db';
import type { Sample, Summary, Worker } from './types';

export interface RegisterInput {
  name: string;
  host: string;
  device: string;
  mode: string;
  network: string;
  wallet: string;
}

export interface HeartbeatInput {
  tops: number;
  solutions: number;
  accepted: number;
  rejected: number;
  uptimeSeconds: number;
  powerWatts?: number;
  gpuUtil?: number;
  gpuTemp?: number;
  gatewayOnline?: boolean;
  networkDifficulty?: number;
}

interface WorkerRow {
  id: string;
  name: string;
  host: string;
  device: string;
  mode: string;
  network: string;
  wallet: string;
  created_at: number;
  last_seen: number;
  tops: number;
  solutions: number;
  accepted: number;
  rejected: number;
  uptime_seconds: number;
  power_watts: number;
  gpu_util: number;
  gpu_temp: number;
  gateway_online: number;
  network_difficulty: number;
}

/**
 * Persists workers and their stats history in SQLite and emits a `change`
 * event whenever the fleet state changes (used to drive WebSocket pushes).
 */
export class Store extends EventEmitter {
  private readonly db: Database.Database;

  constructor(
    dbPath: string,
    private readonly heartbeatTimeoutMs: number,
  ) {
    super();
    this.db = openDatabase(dbPath);
  }

  /** Map a DB row to a Worker, deriving live status from the last heartbeat. */
  private rowToWorker(row: WorkerRow, now = Date.now()): Worker {
    return {
      id: row.id,
      name: row.name,
      host: row.host,
      device: row.device,
      mode: row.mode,
      network: row.network,
      wallet: row.wallet,
      createdAt: row.created_at,
      lastSeen: row.last_seen,
      status: now - row.last_seen <= this.heartbeatTimeoutMs ? 'online' : 'offline',
      tops: row.tops,
      solutions: row.solutions,
      accepted: row.accepted,
      rejected: row.rejected,
      uptimeSeconds: row.uptime_seconds,
      powerWatts: row.power_watts,
      gpuUtil: row.gpu_util,
      gpuTemp: row.gpu_temp,
      gatewayOnline: !!row.gateway_online,
      networkDifficulty: row.network_difficulty,
    };
  }

  registerWorker(input: RegisterInput): Worker {
    const now = Date.now();
    const id = randomUUID();
    this.db
      .prepare(
        `INSERT INTO workers
           (id, name, host, device, mode, network, wallet, created_at, last_seen, status)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'online')`,
      )
      .run(
        id,
        input.name,
        input.host,
        input.device,
        input.mode,
        input.network,
        input.wallet,
        now,
        now,
      );
    this.emit('change');
    return this.getWorker(id)!;
  }

  /** Apply a heartbeat; returns null if the worker id is unknown. */
  heartbeat(id: string, input: HeartbeatInput): Worker | null {
    const now = Date.now();
    const powerWatts = input.powerWatts ?? 0;
    const gpuUtil = input.gpuUtil ?? 0;
    const gpuTemp = input.gpuTemp ?? 0;
    const gatewayOnline = input.gatewayOnline ? 1 : 0;
    const networkDifficulty = input.networkDifficulty ?? 0;
    const result = this.db
      .prepare(
        `UPDATE workers
            SET last_seen = ?, status = 'online', tops = ?,
                solutions = ?, accepted = ?, rejected = ?, uptime_seconds = ?,
                power_watts = ?, gpu_util = ?, gpu_temp = ?,
                gateway_online = ?, network_difficulty = ?
          WHERE id = ?`,
      )
      .run(
        now,
        input.tops,
        input.solutions,
        input.accepted,
        input.rejected,
        input.uptimeSeconds,
        powerWatts,
        gpuUtil,
        gpuTemp,
        gatewayOnline,
        networkDifficulty,
        id,
      );
    if (result.changes === 0) {
      return null;
    }
    this.db
      .prepare(
        `INSERT INTO samples
           (worker_id, ts, tops, solutions, accepted, rejected, uptime_seconds,
            power_watts, gpu_util, gpu_temp)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id,
        now,
        input.tops,
        input.solutions,
        input.accepted,
        input.rejected,
        input.uptimeSeconds,
        powerWatts,
        gpuUtil,
        gpuTemp,
      );
    this.emit('change');
    return this.getWorker(id);
  }

  getWorker(id: string): Worker | null {
    const row = this.db.prepare(`SELECT * FROM workers WHERE id = ?`).get(id) as
      | WorkerRow
      | undefined;
    return row ? this.rowToWorker(row) : null;
  }

  listWorkers(): Worker[] {
    const now = Date.now();
    const rows = this.db
      .prepare(`SELECT * FROM workers ORDER BY name COLLATE NOCASE`)
      .all() as WorkerRow[];
    return rows.map((row) => this.rowToWorker(row, now));
  }

  getHistory(id: string, sinceMs: number): Sample[] {
    return this.db
      .prepare(
        `SELECT ts, tops, solutions, accepted, rejected,
                uptime_seconds AS uptimeSeconds,
                power_watts AS powerWatts, gpu_util AS gpuUtil, gpu_temp AS gpuTemp
           FROM samples
          WHERE worker_id = ? AND ts >= ?
          ORDER BY ts ASC`,
      )
      .all(id, sinceMs) as Sample[];
  }

  summary(): Summary {
    const workers = this.listWorkers();
    const online = workers.filter((w) => w.status === 'online');
    return {
      workerCount: workers.length,
      onlineCount: online.length,
      totalTops: online.reduce((sum, w) => sum + w.tops, 0),
      totalSolutions: workers.reduce((sum, w) => sum + w.solutions, 0),
      totalAccepted: workers.reduce((sum, w) => sum + w.accepted, 0),
      totalRejected: workers.reduce((sum, w) => sum + w.rejected, 0),
      totalPowerWatts: online.reduce((sum, w) => sum + w.powerWatts, 0),
    };
  }

  /** Flag workers whose heartbeats lapsed; emits `change` if any transitioned. */
  markStale(): number {
    const cutoff = Date.now() - this.heartbeatTimeoutMs;
    const result = this.db
      .prepare(`UPDATE workers SET status = 'offline' WHERE status = 'online' AND last_seen < ?`)
      .run(cutoff);
    if (result.changes > 0) {
      this.emit('change');
    }
    return result.changes;
  }

  /** Delete historical samples older than the retention window. */
  pruneHistory(maxAgeMs: number): number {
    const cutoff = Date.now() - maxAgeMs;
    return this.db.prepare(`DELETE FROM samples WHERE ts < ?`).run(cutoff).changes;
  }

  close(): void {
    this.db.close();
  }
}
