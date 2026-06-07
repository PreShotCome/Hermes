import net from 'node:net';
import { randomBytes } from 'node:crypto';

/**
 * A minimal mock Pearl gateway. It speaks the same shape of protocol as the
 * real `pearl-gateway` — newline-delimited JSON-RPC over TCP — with just enough
 * methods (`getMiningInfo`, `submitSolution`) for a worker to mine end-to-end
 * with no `pearld` node, wallet or GPU.
 *
 * It issues real Pearl-style jobs (an incomplete block header + a PoW target)
 * and sanity-checks submitted solutions (claimed transcript hash <= target). It
 * does NOT run full ZK verification or pay rewards, so it is strictly a local
 * demo / test aid — never a real gateway and never a source of PRL.
 */

const PORT = Number(process.env.MOCK_GATEWAY_PORT ?? 3434);
/** Difficulty: target = MAX_TARGET / difficulty. Lower => solutions sooner. */
const DIFFICULTY = BigInt(process.env.MOCK_GATEWAY_DIFFICULTY ?? 2048);
/** How often a fresh job (new header + height) is minted. */
const JOB_INTERVAL_MS = Number(process.env.MOCK_GATEWAY_JOB_INTERVAL_MS ?? 30_000);

const MAX_TARGET = (1n << 256n) - 1n;
const TARGET = MAX_TARGET / (DIFFICULTY > 0n ? DIFFICULTY : 1n);

interface Job {
  job_id: string;
  /** Base64 of an opaque incomplete block header (80 bytes). */
  incomplete_header_bytes: string;
  /** PoW target as a decimal string (a uint256 won't fit a JS number). */
  target: string;
  height: number;
}

let jobCounter = 0;
let currentJob = makeJob();

function makeJob(): Job {
  jobCounter += 1;
  return {
    job_id: `job-${jobCounter}`,
    incomplete_header_bytes: randomBytes(80).toString('base64'),
    target: TARGET.toString(10),
    height: 1 + jobCounter,
  };
}

function log(message: string): void {
  console.log(`[mock-gateway ${new Date().toISOString()}] ${message}`);
}

function writeJson(socket: net.Socket, payload: unknown): void {
  try {
    socket.write(`${JSON.stringify(payload)}\n`);
  } catch {
    /* socket already closed; ignore. */
  }
}

const server = net.createServer((socket) => {
  let buffer = '';
  let accepted = 0;
  socket.setEncoding('utf8');

  const handle = (line: string): void => {
    let msg: { id?: unknown; method?: string; params?: Record<string, unknown> };
    try {
      msg = JSON.parse(line);
    } catch {
      return;
    }
    const id = (msg.id as number | string | null) ?? null;

    switch (msg.method) {
      case 'getMiningInfo':
        writeJson(socket, { jsonrpc: '2.0', id, result: currentJob });
        break;
      case 'submitSolution': {
        const powHash = String(msg.params?.pow_hash ?? '');
        let valid = false;
        try {
          valid = powHash.length > 0 && BigInt(`0x${powHash}`) <= TARGET;
        } catch {
          valid = false;
        }
        if (valid) {
          accepted += 1;
          log(`solution accepted (this connection: ${accepted})`);
        } else {
          log(`solution rejected (hash above target)`);
        }
        writeJson(socket, { jsonrpc: '2.0', id, result: { accepted: valid } });
        break;
      }
      default:
        writeJson(socket, {
          jsonrpc: '2.0',
          id,
          error: { code: -32601, message: `unknown method: ${msg.method}` },
        });
    }
  };

  socket.on('data', (chunk: string) => {
    buffer += chunk;
    let newline = buffer.indexOf('\n');
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) {
        handle(line);
      }
      newline = buffer.indexOf('\n');
    }
  });

  socket.on('error', () => {
    /* connection reset by worker; cleaned up on close. */
  });
});

// Mint a fresh job on a fixed cadence (workers poll getMiningInfo).
setInterval(() => {
  currentJob = makeJob();
}, JOB_INTERVAL_MS);

server.listen(PORT, () => {
  log(`listening on 0.0.0.0:${PORT} (difficulty ${DIFFICULTY}, target 0x${TARGET.toString(16)})`);
});
