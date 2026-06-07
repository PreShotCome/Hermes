import { useEffect, useState } from 'react';
import { fetchSummary, fetchWorkers, WS_URL, type Summary, type Worker } from './api';

export interface FleetState {
  workers: Worker[];
  summary: Summary | null;
  /** True while a live WebSocket feed is connected (vs. REST polling). */
  connected: boolean;
}

/**
 * Subscribe to the fleet's live state. Prefers the server WebSocket and falls
 * back to REST polling whenever the socket is unavailable.
 */
export function useFleet(): FleetState {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const poll = async (): Promise<void> => {
      try {
        const [w, s] = await Promise.all([fetchWorkers(), fetchSummary()]);
        if (!disposed) {
          setWorkers(w);
          setSummary(s);
        }
      } catch {
        /* server unreachable; retry on the next tick. */
      }
    };

    const startPolling = (): void => {
      if (pollTimer === undefined) {
        void poll();
        pollTimer = setInterval(() => void poll(), 5_000);
      }
    };

    const stopPolling = (): void => {
      if (pollTimer !== undefined) {
        clearInterval(pollTimer);
        pollTimer = undefined;
      }
    };

    const connect = (): void => {
      if (disposed) {
        return;
      }
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        setConnected(true);
        stopPolling();
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string);
          if (message.type === 'snapshot') {
            setWorkers(message.workers as Worker[]);
            setSummary(message.summary as Summary);
          }
        } catch {
          /* ignore malformed frames. */
        }
      };

      socket.onclose = () => {
        setConnected(false);
        startPolling();
        if (!disposed) {
          reconnectTimer = setTimeout(connect, 5_000);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    startPolling(); // show data immediately while the socket connects.
    connect();

    return () => {
      disposed = true;
      stopPolling();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, []);

  return { workers, summary, connected };
}
