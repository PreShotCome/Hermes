import type { Server } from 'node:http';
import { WebSocket, WebSocketServer } from 'ws';
import type { Store } from './store';

/**
 * Attach a WebSocket endpoint at `/ws`. Each client receives a full fleet
 * snapshot on connect and again whenever the store reports a change.
 */
export function attachWebSocket(server: Server, store: Store): WebSocketServer {
  const wss = new WebSocketServer({ server, path: '/ws' });

  const snapshot = (): string =>
    JSON.stringify({
      type: 'snapshot',
      workers: store.listWorkers(),
      summary: store.summary(),
    });

  wss.on('connection', (socket) => {
    socket.send(snapshot());
  });

  const broadcast = (): void => {
    const message = snapshot();
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  };

  store.on('change', broadcast);
  return wss;
}
