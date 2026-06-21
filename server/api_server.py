"""FastAPI surface over the Hermes server.

Auth: a shared header (`x-api-key`) that matches `HERMES_API_KEY` in .env.
Every endpoint is paper-mode. There is no place-a-real-bet endpoint.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server import HermesServer, scan_loop


load_dotenv()
API_KEY = os.getenv('HERMES_API_KEY', 'hermes-dev-key-change-me')

_server: HermesServer | None = None


def _hermes() -> HermesServer:
    assert _server is not None, 'server not initialized'
    return _server


def _check_key(x_api_key: str | None) -> None:
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail='bad api key')


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    global _server
    _server = HermesServer()
    task = asyncio.create_task(scan_loop(_server))
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title='Hermes', version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_methods=['*'], allow_headers=['*'],
)


# ── schemas ──────────────────────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    key: str
    value: Any


class SettleBody(BaseModel):
    result: str  # won | lost | push


class ChatBody(BaseModel):
    message: str


# ── routes ───────────────────────────────────────────────────────────────────

@app.get('/health')
async def health():
    return {'ok': True}


@app.get('/bankroll')
async def get_bankroll(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return _hermes().bankroll()


@app.get('/status')
async def get_status(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return _hermes().status()


@app.get('/equity')
async def get_equity(limit: int = Query(500, ge=1, le=2000),
                     x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return {'curve': _hermes().equity_curve(limit=limit)}


@app.get('/picks')
async def get_picks(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return {'picks': _hermes().picks()}


@app.post('/scan')
async def post_scan(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return await _hermes().scan()


@app.post('/picks/{pick_id}/place')
async def place_pick(pick_id: str,
                     x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    try:
        return _hermes().place_pick(pick_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        # Blocked by risk_engine.validate_bet. No override path.
        raise HTTPException(status_code=409, detail=str(e))


@app.post('/picks/{pick_id}/skip')
async def skip_pick(pick_id: str,
                    x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return _hermes().skip_pick(pick_id)


@app.get('/bets')
async def get_bets(limit: int = Query(100, ge=1, le=500),
                   status: str | None = Query(default=None),
                   x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return {'bets': _hermes().bets(limit=limit, status=status)}


@app.post('/bets/{bet_id}/settle')
async def settle_bet(bet_id: str, body: SettleBody,
                     x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    try:
        return _hermes().settle_bet(bet_id, body.result)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/settings')
async def get_settings(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return _hermes().settings()


@app.post('/settings')
async def post_settings(body: SettingUpdate,
                        x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    try:
        _hermes().update_setting(body.key, body.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {'ok': True}


@app.post('/pause')
async def post_pause(x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    return {'paused': _hermes().toggle_pause()}


# ── Oracle (AI assistant) ────────────────────────────────────────────────────

@app.post('/chat')
async def post_chat(body: ChatBody,
                    x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    reply = await _oracle_reply(body.message, _hermes())
    return {'reply': reply}


async def _oracle_reply(message: str, hermes: HermesServer) -> str:
    """Anthropic-backed Oracle. If no key is set, fall back to a deterministic
    summary so the chat UI still works in dev."""
    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    context = _oracle_context(hermes)
    if not api_key:
        return _fallback_reply(message, context)
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=api_key)
        sys_prompt = (
            'You are the Oracle of Hermes, a calm and concise advisor for a '
            'paper sports-betting app. You see only the supplied context; '
            'never invent picks, bets, or numbers not provided. Be specific, '
            'short (under 120 words), and refuse anything that asks you to '
            'override risk limits or place real-money bets.'
        )
        # claude-haiku-4-5 — fast, cheap, perfect for short advisor turns.
        msg = await client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=400,
            system=sys_prompt,
            messages=[{
                'role': 'user',
                'content': f'CONTEXT:\n{context}\n\nUSER:\n{message}',
            }],
        )
        parts = []
        for block in msg.content:
            if getattr(block, 'type', '') == 'text':
                parts.append(block.text)
        return ''.join(parts) or _fallback_reply(message, context)
    except Exception as exc:
        return f'Oracle error: {exc}\n\n{_fallback_reply(message, context)}'


def _oracle_context(h: HermesServer) -> str:
    bk = h.bankroll()
    st = h.status()
    picks = h.picks()[:5]
    recent = h.bets(limit=5)
    settings = h.settings()
    lines = [
        f'Bankroll ${bk["balance"]:.2f}  starting ${bk["starting"]:.2f}  '
        f'day P&L ${bk["day_pnl"]:.2f}  open {bk["open_bets"]}  '
        f'win rate {bk["win_rate"]*100:.1f}%',
        f'Mode {st["mode"]}  paused={st["paused"]}  '
        f'sharp_api_live={st["sharp_api_live"]}  sports={settings.get("sports")}',
        f'Risk: kelly={settings["kelly_fraction"]}  '
        f'min_edge={settings["min_edge"]}  '
        f'max_bet_pct={settings["max_bet_pct"]}  '
        f'daily_loss_pct={settings["daily_loss_pct"]}',
        'Current picks:',
    ]
    if not picks:
        lines.append('  (none)')
    for p in picks:
        lines.append(
            f'  - {p["selection"]} ({p["matchup"]}, {p["book"]}) '
            f'{p["american_odds"]:+d}  edge {p["edge"]*100:.1f}%  '
            f'stake ${p["stake"]:.2f}'
        )
    lines.append('Recent bets:')
    if not recent:
        lines.append('  (none)')
    for b in recent:
        lines.append(
            f'  - {b["status"].upper()} {b["selection"]} ({b["matchup"]}) '
            f'{b["american_odds"]:+d}  stake ${b["stake"]:.2f}  '
            f'payout ${b["payout"]:.2f}'
        )
    return '\n'.join(lines)


def _fallback_reply(message: str, context: str) -> str:
    return (
        'I have no Anthropic key on the server, so I can only mirror what I see:\n\n'
        + context
    )
