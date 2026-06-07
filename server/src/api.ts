import { Router } from 'express';
import { z } from 'zod';
import type { Store } from './store';

const registerSchema = z.object({
  name: z.string().min(1).max(64),
  host: z.string().min(1).max(128),
  device: z.string().max(128).default(''),
  mode: z.string().max(32).default('reference'),
  network: z.string().max(32).default(''),
  wallet: z.string().max(128).default(''),
});

const heartbeatSchema = z.object({
  tops: z.coerce.number().min(0),
  solutions: z.coerce.number().int().min(0),
  accepted: z.coerce.number().int().min(0),
  rejected: z.coerce.number().int().min(0),
  uptimeSeconds: z.coerce.number().int().min(0),
  powerWatts: z.coerce.number().min(0).default(0),
  gpuUtil: z.coerce.number().min(0).default(0),
  gpuTemp: z.coerce.number().default(0),
});

/** Build the REST API router backed by the given store. */
export function createApiRouter(store: Store): Router {
  const router = Router();

  router.get('/health', (_req, res) => {
    res.json({ status: 'ok' });
  });

  router.post('/workers/register', (req, res) => {
    const parsed = registerSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'invalid registration', details: parsed.error.issues });
      return;
    }
    const worker = store.registerWorker(parsed.data);
    res.status(201).json(worker);
  });

  router.post('/workers/:id/heartbeat', (req, res) => {
    const parsed = heartbeatSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'invalid heartbeat', details: parsed.error.issues });
      return;
    }
    const worker = store.heartbeat(req.params.id, parsed.data);
    if (!worker) {
      res.status(404).json({ error: 'unknown worker' });
      return;
    }
    res.json(worker);
  });

  router.get('/workers', (_req, res) => {
    res.json(store.listWorkers());
  });

  router.get('/workers/:id', (req, res) => {
    const worker = store.getWorker(req.params.id);
    if (!worker) {
      res.status(404).json({ error: 'unknown worker' });
      return;
    }
    res.json(worker);
  });

  router.get('/workers/:id/history', (req, res) => {
    if (!store.getWorker(req.params.id)) {
      res.status(404).json({ error: 'unknown worker' });
      return;
    }
    const minutes = Math.min(Math.max(Number(req.query.minutes) || 60, 1), 1440);
    const since = Date.now() - minutes * 60_000;
    res.json(store.getHistory(req.params.id, since));
  });

  router.get('/stats/summary', (_req, res) => {
    res.json(store.summary());
  });

  return router;
}
