import { describe, expect, it } from 'vitest';
import { Store } from './store';

const TIMEOUT = 10_000;

function freshStore(): Store {
  return new Store(':memory:', TIMEOUT);
}

function register(store: Store, name = 'rig') {
  return store.registerWorker({
    name,
    host: 'localhost',
    device: 'cpu (numpy)',
    mode: 'reference',
    network: 'mock',
    wallet: '',
  });
}

describe('Store', () => {
  it('registers a worker and reads it back', () => {
    const store = freshStore();
    const worker = register(store, 'alpha');
    expect(worker.id).toBeTruthy();
    expect(worker.status).toBe('online');
    expect(worker.mode).toBe('reference');
    expect(store.getWorker(worker.id)?.name).toBe('alpha');
    store.close();
  });

  it('applies heartbeats and records history', () => {
    const store = freshStore();
    const worker = register(store);
    const updated = store.heartbeat(worker.id, {
      tops: 1.25,
      solutions: 5,
      accepted: 3,
      rejected: 1,
      uptimeSeconds: 60,
    });
    expect(updated?.tops).toBe(1.25);
    expect(updated?.solutions).toBe(5);
    expect(updated?.accepted).toBe(3);
    expect(store.getHistory(worker.id, 0)).toHaveLength(1);
    store.close();
  });

  it('rejects heartbeats for unknown workers', () => {
    const store = freshStore();
    expect(
      store.heartbeat('does-not-exist', {
        tops: 1,
        solutions: 0,
        accepted: 0,
        rejected: 0,
        uptimeSeconds: 0,
      }),
    ).toBeNull();
    store.close();
  });

  it('aggregates a fleet summary across workers', () => {
    const store = freshStore();
    const a = register(store, 'a');
    const b = register(store, 'b');
    store.heartbeat(a.id, { tops: 1.0, solutions: 5, accepted: 5, rejected: 1, uptimeSeconds: 10 });
    store.heartbeat(b.id, { tops: 2.5, solutions: 7, accepted: 7, rejected: 0, uptimeSeconds: 10 });
    const summary = store.summary();
    expect(summary.workerCount).toBe(2);
    expect(summary.onlineCount).toBe(2);
    expect(summary.totalTops).toBe(3.5);
    expect(summary.totalSolutions).toBe(12);
    expect(summary.totalAccepted).toBe(12);
    expect(summary.totalRejected).toBe(1);
    store.close();
  });

  it('marks a worker offline once its heartbeat lapses', () => {
    const store = new Store(':memory:', -1); // negative timeout => instantly stale
    const worker = register(store);
    expect(store.getWorker(worker.id)?.status).toBe('offline');
    expect(store.markStale()).toBe(1);
    expect(store.markStale()).toBe(0); // idempotent once transitioned
    store.close();
  });

  it('emits a change event on registration and heartbeat', () => {
    const store = freshStore();
    let changes = 0;
    store.on('change', () => {
      changes += 1;
    });
    const worker = register(store);
    store.heartbeat(worker.id, {
      tops: 1,
      solutions: 0,
      accepted: 0,
      rejected: 0,
      uptimeSeconds: 1,
    });
    expect(changes).toBe(2);
    store.close();
  });
});
