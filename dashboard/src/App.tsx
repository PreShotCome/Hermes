import { useState } from 'react';
import { useFleet } from './useFleet';
import { SummaryBar } from './components/SummaryBar';
import { WorkerCard } from './components/WorkerCard';
import { WorkerDetail } from './components/WorkerDetail';

export function App() {
  const { workers, summary, connected } = useFleet();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = workers.find((w) => w.id === selectedId) ?? null;

  return (
    <div className="app">
      <header className="app-header">
        <h1>
          <span className="logo" aria-hidden="true">
            🦪
          </span>
          Pearl Mining Monitor
        </h1>
        <span
          className={`conn ${connected ? 'conn-live' : 'conn-poll'}`}
          title={connected ? 'Live WebSocket feed' : 'Polling the REST API'}
        >
          {connected ? 'live' : 'polling'}
        </span>
      </header>

      <SummaryBar summary={summary} />

      {workers.length === 0 ? (
        <p className="empty">
          No workers yet. Start a Pearl worker and it will appear here automatically.
        </p>
      ) : (
        <div className="grid">
          {workers.map((worker) => (
            <WorkerCard
              key={worker.id}
              worker={worker}
              onSelect={() => setSelectedId(worker.id)}
            />
          ))}
        </div>
      )}

      {selected && (
        <WorkerDetail worker={selected} onClose={() => setSelectedId(null)} />
      )}

      <footer className="app-footer">
        Monitoring {workers.length} worker{workers.length === 1 ? '' : 's'}
        {' · '}
        {connected ? 'live updates' : 'reconnecting…'}
      </footer>
    </div>
  );
}
