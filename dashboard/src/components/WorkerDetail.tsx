import { useEffect } from 'react';
import type { Worker } from '../api';
import {
  formatTops,
  formatNumber,
  formatUptime,
  formatWatts,
  formatEfficiency,
  formatTemp,
} from '../format';
import { RateChart } from './RateChart';

export function WorkerDetail({
  worker,
  onClose,
}: {
  worker: Worker;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Worker ${worker.name}`}
      >
        <div className="modal-head">
          <h2>
            <span className={`dot dot-${worker.status}`} aria-hidden="true" />
            {worker.name}
          </h2>
          <button className="close" onClick={onClose} type="button" aria-label="Close">
            ×
          </button>
        </div>

        <div className="detail-stats">
          <Tile label="Throughput" value={formatTops(worker.tops)} accent />
          <Tile label="Power" value={formatWatts(worker.powerWatts)} />
          <Tile
            label="Efficiency"
            value={formatEfficiency(worker.tops, worker.powerWatts)}
            accent
          />
          <Tile label="GPU util" value={worker.gpuUtil > 0 ? `${worker.gpuUtil.toFixed(0)}%` : '—'} />
          <Tile label="GPU temp" value={formatTemp(worker.gpuTemp)} />
          <Tile label="Mode" value={worker.mode} />
          <Tile label="Solutions" value={formatNumber(worker.solutions)} />
          <Tile label="Accepted" value={formatNumber(worker.accepted)} />
          <Tile label="Uptime" value={formatUptime(worker.uptimeSeconds)} />
        </div>

        {worker.mode === 'reference' && (
          <p className="note">
            Reference mode: this worker runs real Pearl matmul proof-of-useful-work and
            verifies solutions locally, but does not submit ZK proofs to a node — so it
            earns no PRL. Switch to <code>--mode live</code> against a synced pearld node
            (and a GPU) to mine for rewards.
          </p>
        )}

        <h3>Throughput (last hour)</h3>
        <RateChart workerId={worker.id} />

        <dl className="detail-meta">
          <div className="row">
            <dt>Host</dt>
            <dd>{worker.host}</dd>
          </div>
          <div className="row">
            <dt>Device</dt>
            <dd>{worker.device}</dd>
          </div>
          <div className="row">
            <dt>Network</dt>
            <dd>{worker.network}</dd>
          </div>
          {worker.wallet && (
            <div className="row">
              <dt>Wallet</dt>
              <dd>{worker.wallet}</dd>
            </div>
          )}
          <div className="row">
            <dt>Last seen</dt>
            <dd>{new Date(worker.lastSeen).toLocaleString()}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

function Tile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="tile">
      <div className={`tile-value${accent ? ' accent' : ''}`}>{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}
