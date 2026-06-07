import type { Worker } from '../api';
import { formatTops, formatNumber, formatUptime } from '../format';

export function WorkerCard({
  worker,
  onSelect,
}: {
  worker: Worker;
  onSelect: () => void;
}) {
  const modeClass = worker.mode === 'live' ? 'badge-live' : 'badge-reference';
  return (
    <button className="card" onClick={onSelect} type="button">
      <div className="card-head">
        <span className={`dot dot-${worker.status}`} aria-hidden="true" />
        <span className="card-name">{worker.name}</span>
        <span className={`badge ${modeClass}`}>{worker.mode}</span>
      </div>
      <div className="card-rate">{formatTops(worker.tops)}</div>
      <dl className="card-rows">
        <Row label="Status" value={worker.status} />
        <Row label="Device" value={worker.device} />
        <Row label="Network" value={worker.network} />
        <Row label="Solutions" value={formatNumber(worker.solutions)} />
        <Row label="Accepted" value={formatNumber(worker.accepted)} />
        <Row label="Uptime" value={formatUptime(worker.uptimeSeconds)} />
      </dl>
    </button>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
