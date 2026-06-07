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
