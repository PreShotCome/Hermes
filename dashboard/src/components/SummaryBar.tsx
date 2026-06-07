import type { Summary } from '../api';
import { formatTops, formatNumber } from '../format';

const EMPTY: Summary = {
  workerCount: 0,
  onlineCount: 0,
  totalTops: 0,
  totalSolutions: 0,
  totalAccepted: 0,
  totalRejected: 0,
};

export function SummaryBar({ summary }: { summary: Summary | null }) {
  const s = summary ?? EMPTY;
  return (
    <div className="summary">
      <Stat label="Total throughput" value={formatTops(s.totalTops)} accent />
      <Stat label="Workers online" value={`${s.onlineCount} / ${s.workerCount}`} />
      <Stat label="Solutions found" value={formatNumber(s.totalSolutions)} />
      <Stat label="Blocks accepted" value={formatNumber(s.totalAccepted)} />
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="stat">
      <div className={`stat-value${accent ? ' accent' : ''}`}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
