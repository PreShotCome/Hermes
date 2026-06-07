/** Format an int8 matmul throughput in tera-ops/sec with a sensible unit. */
export function formatTops(tops: number): string {
  if (!Number.isFinite(tops) || tops <= 0) {
    return '0 TOPS';
  }
  if (tops < 0.001) {
    return `${(tops * 1_000_000).toFixed(1)} MOPS`;
  }
  if (tops < 1) {
    return `${(tops * 1_000).toFixed(2)} GOPS`;
  }
  if (tops < 1_000) {
    return `${tops.toFixed(2)} TOPS`;
  }
  return `${(tops / 1_000).toFixed(2)} POPS`;
}

/** Format an uptime in seconds as a compact human-readable string. */
export function formatUptime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '0s';
  }
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  const secs = Math.floor(seconds % 60);

  const parts: string[] = [];
  if (days) parts.push(`${days}d`);
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  if (!days && !hours) parts.push(`${secs}s`);
  return parts.join(' ');
}

/** Format an integer with thousands separators. */
export function formatNumber(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

/** Format a GPU power draw in watts. */
export function formatWatts(watts: number): string {
  if (!Number.isFinite(watts) || watts <= 0) {
    return '—';
  }
  if (watts < 1000) {
    return `${watts.toFixed(0)} W`;
  }
  return `${(watts / 1000).toFixed(2)} kW`;
}

/**
 * Power efficiency: matmul throughput per watt. This is the number to maximize
 * to save on electricity — more useful work for the same power.
 */
export function formatEfficiency(tops: number, watts: number): string {
  if (!Number.isFinite(watts) || watts <= 0 || tops <= 0) {
    return '—';
  }
  const topsPerWatt = tops / watts;
  if (topsPerWatt >= 1) {
    return `${topsPerWatt.toFixed(2)} TOPS/W`;
  }
  if (topsPerWatt >= 0.001) {
    return `${(topsPerWatt * 1000).toFixed(1)} GOPS/W`;
  }
  return `${(topsPerWatt * 1_000_000).toFixed(1)} MOPS/W`;
}

/** Format a temperature in °C. */
export function formatTemp(celsius: number): string {
  if (!Number.isFinite(celsius) || celsius <= 0) {
    return '—';
  }
  return `${celsius.toFixed(0)}°C`;
}

/** Format a (potentially astronomical) network difficulty compactly. */
export function formatDifficulty(difficulty: number): string {
  if (!Number.isFinite(difficulty) || difficulty <= 0) {
    return '—';
  }
  if (difficulty < 1000) {
    return difficulty.toFixed(0);
  }
  return difficulty.toExponential(2);
}
