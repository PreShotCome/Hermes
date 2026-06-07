export type WorkerStatus = 'online' | 'offline';

export interface Worker {
  id: string;
  name: string;
  host: string;
  device: string;
  mode: string;
  network: string;
  wallet: string;
  createdAt: number;
  lastSeen: number;
  status: WorkerStatus;
  tops: number;
  solutions: number;
  accepted: number;
  rejected: number;
  uptimeSeconds: number;
  powerWatts: number;
  gpuUtil: number;
  gpuTemp: number;
}

export interface Sample {
  ts: number;
  tops: number;
  solutions: number;
  accepted: number;
  rejected: number;
  uptimeSeconds: number;
  powerWatts: number;
  gpuUtil: number;
  gpuTemp: number;
}

export interface Summary {
  workerCount: number;
  onlineCount: number;
  totalTops: number;
  totalSolutions: number;
  totalAccepted: number;
  totalRejected: number;
  totalPowerWatts: number;
}

/** Base URL of the monitoring server; overridable at build time. */
export const SERVER_URL = (
  import.meta.env.VITE_SERVER_URL ?? 'http://localhost:4000'
).replace(/\/$/, '');

/** WebSocket URL derived from the server URL. */
export const WS_URL = `${SERVER_URL.replace(/^http/, 'ws')}/ws`;

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${SERVER_URL}${path}`);
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const fetchWorkers = (): Promise<Worker[]> => getJson('/api/workers');

export const fetchSummary = (): Promise<Summary> => getJson('/api/stats/summary');

export const fetchHistory = (id: string, minutes = 60): Promise<Sample[]> =>
  getJson(`/api/workers/${id}/history?minutes=${minutes}`);
