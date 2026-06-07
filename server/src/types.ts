export type WorkerStatus = 'online' | 'offline';

/** A Pearl miner instance and its most recent reported stats. */
export interface Worker {
  id: string;
  name: string;
  host: string;
  /** Compute device, e.g. "cpu (numpy)" or "NVIDIA RTX 4090". */
  device: string;
  /** "reference" (CPU, earns nothing) or "live" (submits to a real node). */
  mode: string;
  /** Network label: mock | mainnet | testnet | ... */
  network: string;
  /** Payout address (live mode); empty in reference mode. */
  wallet: string;
  createdAt: number;
  lastSeen: number;
  status: WorkerStatus;
  /** int8 matmul throughput in tera-ops/sec (Pearl's analogue of hashrate). */
  tops: number;
  /** PoUW solutions found (winning transcripts). */
  solutions: number;
  /** Solutions accepted by the gateway / chain (blocks, in live mode). */
  accepted: number;
  /** Solutions rejected. */
  rejected: number;
  uptimeSeconds: number;
  /** GPU board power draw in watts (0 if no GPU telemetry). */
  powerWatts: number;
  /** GPU utilization percentage. */
  gpuUtil: number;
  /** GPU temperature in °C. */
  gpuTemp: number;
}

/** A single historical stats reading for one worker. */
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

/** Fleet-wide aggregate across all known workers. */
export interface Summary {
  workerCount: number;
  onlineCount: number;
  totalTops: number;
  totalSolutions: number;
  totalAccepted: number;
  totalRejected: number;
  /** Total GPU power draw across online workers (watts). */
  totalPowerWatts: number;
}
