"""Hermes bot — persistence, scan loop, and the operations the API exposes.

This is the brain of the server. Everything stateful lives here:

  * SQLite ledger (bets, picks, equity snapshots, settings)
  * Periodic scan loop that fetches odds, runs the model, and surfaces picks
  * Bet-placing path that runs through `validate_bet` before recording
  * Settlement, which updates Elo ratings and the equity curve

The HTTP layer (`api_server.py`) is a thin wrapper over the methods here.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from odds_client import OddsClient, american_to_decimal
from prediction_engine import PredictionEngine, Prediction
from risk_engine import RiskLimits, RiskState, validate_bet
from value_engine import ValueBet, find_value_bets


DATA_DIR    = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH     = os.path.join(DATA_DIR, 'hermes.db')
STATE_PATH  = os.path.join(DATA_DIR, 'ratings.json')

DEFAULT_SETTINGS: dict[str, Any] = {
    'paused':           False,
    'kelly_fraction':   0.25,   # ¼-Kelly — the only sane default
    'min_edge':         0.03,   # 3% over de-vigged fair
    'max_bet_pct':      0.02,   # 2% of bankroll per bet, hard cap
    'daily_loss_pct':   0.08,   # halt after -8% on the day
    'min_bankroll':     50.0,
    'max_concurrent':   12,
    'max_total_exposure_pct': 0.20,  # 20% of bankroll across all open bets
    'sports':           ['NFL', 'NBA', 'MLB', 'NHL'],
}


# ── DB helpers ───────────────────────────────────────────────────────────────

def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS picks (
            id            TEXT PRIMARY KEY,
            created_at    TEXT NOT NULL,
            status        TEXT NOT NULL,  -- pending | placed | skipped | expired
            sport         TEXT NOT NULL,
            matchup       TEXT NOT NULL,
            book          TEXT NOT NULL,
            event_id      TEXT NOT NULL,
            commences_at  TEXT NOT NULL,
            selection     TEXT NOT NULL,
            side          TEXT NOT NULL,
            american_odds INTEGER NOT NULL,
            decimal_odds  REAL NOT NULL,
            model_prob    REAL NOT NULL,
            market_prob   REAL NOT NULL,
            edge          REAL NOT NULL,
            ev_per_dollar REAL NOT NULL,
            stake         REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bets (
            id            TEXT PRIMARY KEY,
            pick_id       TEXT,
            placed_at     TEXT NOT NULL,
            settled_at    TEXT,
            status        TEXT NOT NULL,  -- open | won | lost | push
            sport         TEXT NOT NULL,
            matchup       TEXT NOT NULL,
            book          TEXT NOT NULL,
            event_id      TEXT NOT NULL,
            commences_at  TEXT NOT NULL,
            home_team     TEXT NOT NULL,
            away_team     TEXT NOT NULL,
            selection     TEXT NOT NULL,
            side          TEXT NOT NULL,
            american_odds INTEGER NOT NULL,
            decimal_odds  REAL NOT NULL,
            model_prob    REAL NOT NULL,
            stake         REAL NOT NULL,
            payout        REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS equity (
            ts        TEXT PRIMARY KEY,
            balance   REAL NOT NULL
        );
    ''')
    conn.commit()


@contextmanager
def _connect(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {k: r[k] for k in r.keys()}


# ── Main server object ──────────────────────────────────────────────────────

class HermesServer:
    """Owns the engine state. One instance per process."""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with _connect() as conn:
            _init_db(conn)
        self.odds = OddsClient()
        self.predictor = PredictionEngine(STATE_PATH)
        self._settings = self._load_settings()
        self.starting_bankroll = float(os.getenv('STARTING_BANKROLL', '1000') or 1000.0)
        self._scan_lock = asyncio.Lock()
        self._last_scan_at: float | None = None
        self._last_scan_found: int = 0

    # ── settings ─────────────────────────────────────────────────────────────

    def _load_settings(self) -> dict[str, Any]:
        out = dict(DEFAULT_SETTINGS)
        with _connect() as conn:
            for row in conn.execute('SELECT key, value FROM settings'):
                try:
                    out[row['key']] = json.loads(row['value'])
                except Exception:
                    pass
        return out

    def settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def update_setting(self, key: str, value: Any) -> None:
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f'Unknown setting: {key}')
        self._settings[key] = value
        with _connect() as conn:
            conn.execute(
                'INSERT INTO settings(key, value) VALUES(?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                (key, json.dumps(value)),
            )
            conn.commit()

    def toggle_pause(self) -> bool:
        self.update_setting('paused', not bool(self._settings.get('paused')))
        return bool(self._settings.get('paused'))

    # ── bankroll & status ────────────────────────────────────────────────────

    def bankroll(self) -> dict[str, Any]:
        with _connect() as conn:
            settled = conn.execute(
                "SELECT IFNULL(SUM(payout), 0) AS pnl "
                "FROM bets WHERE status IN ('won','lost','push')"
            ).fetchone()['pnl']
            day_pnl = self._day_pnl(conn)
            open_count = conn.execute(
                "SELECT COUNT(*) AS n FROM bets WHERE status = 'open'"
            ).fetchone()['n']
            settled_today = conn.execute(
                "SELECT COUNT(*) AS n FROM bets "
                "WHERE status IN ('won','lost','push') "
                "AND settled_at >= ?",
                (self._local_midnight_iso(),),
            ).fetchone()['n']
            wins = conn.execute(
                "SELECT COUNT(*) AS n FROM bets WHERE status = 'won'"
            ).fetchone()['n']
            settled_total = conn.execute(
                "SELECT COUNT(*) AS n FROM bets "
                "WHERE status IN ('won','lost')"
            ).fetchone()['n']
        balance = self.starting_bankroll + float(settled)
        win_rate = (wins / settled_total) if settled_total else 0.0
        return {
            'balance':       balance,
            'starting':      self.starting_bankroll,
            'day_pnl':       day_pnl,
            'open_bets':     open_count,
            'settled_today': settled_today,
            'win_rate':      win_rate,
        }

    def status(self) -> dict[str, Any]:
        return {
            'mode':           'paper',  # always paper — we never place real bets
            'paused':         bool(self._settings.get('paused')),
            'odds_live':      self.odds.live,
            'last_scan_at':   self._last_scan_at,
            'last_scan_found': self._last_scan_found,
        }

    def equity_curve(self, limit: int = 500) -> list[dict[str, Any]]:
        with _connect() as conn:
            rows = conn.execute(
                'SELECT ts, balance FROM equity ORDER BY ts DESC LIMIT ?',
                (limit,),
            ).fetchall()
        rows = list(reversed(rows))
        return [{'ts': r['ts'], 'balance': r['balance']} for r in rows]

    # ── scan / picks ─────────────────────────────────────────────────────────

    async def scan(self) -> dict[str, Any]:
        """Fetch markets, run the model, store fresh value picks."""
        async with self._scan_lock:
            sports = list(self._settings.get('sports') or [])
            markets = await self.odds.fetch_markets(sports)
            predictions: dict[str, Prediction] = {
                m.event_id: self.predictor.predict(m.sport, m.home_team, m.away_team)
                for m in markets
            }
            bankroll = self.bankroll()['balance']
            value_bets = find_value_bets(
                markets, predictions,
                bankroll=bankroll,
                min_edge=float(self._settings['min_edge']),
                kelly_fraction=float(self._settings['kelly_fraction']),
                max_bet_pct=float(self._settings['max_bet_pct']),
            )
            self._store_picks(value_bets)
            self._last_scan_at = time.time()
            self._last_scan_found = len(value_bets)
            return {
                'found':           len(value_bets),
                'markets_scanned': len(markets),
                'sports':          sports,
            }

    def _store_picks(self, bets: list[ValueBet]) -> None:
        """Replace pending picks with this scan's results.

        Anything that was pending and isn't in the new scan is dropped — the
        line moved or the value evaporated, so we don't want stale picks
        haunting the UI.
        """
        now = datetime.now(timezone.utc).isoformat()
        with _connect() as conn:
            conn.execute("DELETE FROM picks WHERE status = 'pending'")
            for b in bets:
                conn.execute(
                    'INSERT INTO picks(id, created_at, status, sport, matchup, book,'
                    ' event_id, commences_at, selection, side, american_odds, decimal_odds,'
                    ' model_prob, market_prob, edge, ev_per_dollar, stake) '
                    'VALUES (?, ?, "pending", ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        str(uuid.uuid4()), now,
                        b.sport, b.matchup, b.book,
                        b.event_id, b.commences_at,
                        b.selection, b.side,
                        b.american_odds, b.decimal_odds,
                        b.model_prob, b.market_prob,
                        b.edge, b.expected_value, b.stake,
                    ),
                )
            conn.commit()

    def picks(self) -> list[dict[str, Any]]:
        with _connect() as conn:
            rows = conn.execute(
                'SELECT * FROM picks WHERE status = "pending" '
                'ORDER BY edge DESC',
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── placing / settling bets ──────────────────────────────────────────────

    def place_pick(self, pick_id: str) -> dict[str, Any]:
        """Validate and record a paper bet from a pending pick."""
        with _connect() as conn:
            row = conn.execute(
                'SELECT * FROM picks WHERE id = ? AND status = "pending"',
                (pick_id,),
            ).fetchone()
        if row is None:
            raise LookupError('Pick not found or already actioned.')

        bet = ValueBet(
            sport=row['sport'], matchup=row['matchup'], book=row['book'],
            selection=row['selection'], side=row['side'],
            event_id=row['event_id'], commences_at=row['commences_at'],
            american_odds=row['american_odds'], decimal_odds=row['decimal_odds'],
            model_prob=row['model_prob'], market_prob=row['market_prob'],
            edge=row['edge'], expected_value=row['ev_per_dollar'],
            stake=row['stake'],
        )

        block = validate_bet(bet, self._risk_state(), self._risk_limits())
        if block is not None:
            # Surface the block reason to the caller. There is no override.
            raise PermissionError(f'{block.code}: {block.reason}')

        bet_id = str(uuid.uuid4())
        # We synthesize home/away team names from the matchup string ("X @ Y").
        away, _, home = row['matchup'].partition(' @ ')
        with _connect() as conn:
            conn.execute(
                'INSERT INTO bets(id, pick_id, placed_at, status, sport, matchup, book,'
                ' event_id, commences_at, home_team, away_team, selection, side,'
                ' american_odds, decimal_odds, model_prob, stake) '
                'VALUES (?, ?, ?, "open", ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    bet_id, pick_id,
                    datetime.now(timezone.utc).isoformat(),
                    row['sport'], row['matchup'], row['book'],
                    row['event_id'], row['commences_at'],
                    home.strip(), away.strip(),
                    row['selection'], row['side'],
                    row['american_odds'], row['decimal_odds'],
                    row['model_prob'], row['stake'],
                ),
            )
            conn.execute(
                'UPDATE picks SET status = "placed" WHERE id = ?', (pick_id,),
            )
            conn.commit()

        return {
            'id':           bet_id,
            'stake':        bet.stake,
            'stake_pretty': f'${bet.stake:.2f} @ {bet.american_odds:+d}',
        }

    def skip_pick(self, pick_id: str) -> dict[str, Any]:
        with _connect() as conn:
            conn.execute(
                'UPDATE picks SET status = "skipped" WHERE id = ? AND status = "pending"',
                (pick_id,),
            )
            conn.commit()
        return {'ok': True}

    def settle_bet(self, bet_id: str, result: str) -> dict[str, Any]:
        if result not in ('won', 'lost', 'push'):
            raise ValueError('result must be won | lost | push')
        with _connect() as conn:
            row = conn.execute(
                'SELECT * FROM bets WHERE id = ? AND status = "open"', (bet_id,),
            ).fetchone()
            if row is None:
                raise LookupError('Open bet not found.')
            stake  = float(row['stake'])
            decimal_odds = float(row['decimal_odds'])
            if result == 'won':
                payout = stake * (decimal_odds - 1.0)
            elif result == 'lost':
                payout = -stake
            else:
                payout = 0.0
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                'UPDATE bets SET status = ?, settled_at = ?, payout = ? WHERE id = ?',
                (result, now, payout, bet_id),
            )
            conn.commit()

        # Update Elo when we know the outcome. Push doesn't move ratings.
        if result in ('won', 'lost'):
            home_won = (result == 'won' and row['side'] == 'home') or \
                       (result == 'lost' and row['side'] == 'away')
            self.predictor.update_after_result(
                row['sport'], row['home_team'], row['away_team'], home_won,
            )

        self._snapshot_equity()
        return {'id': bet_id, 'payout': payout, 'status': result}

    def bets(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        sql = 'SELECT * FROM bets'
        params: list[Any] = []
        if status:
            sql += ' WHERE status = ?'
            params.append(status)
        sql += ' ORDER BY placed_at DESC LIMIT ?'
        params.append(limit)
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── helpers ──────────────────────────────────────────────────────────────

    def _snapshot_equity(self) -> None:
        bk = self.bankroll()['balance']
        with _connect() as conn:
            conn.execute(
                'INSERT INTO equity(ts, balance) VALUES (?, ?) '
                'ON CONFLICT(ts) DO UPDATE SET balance = excluded.balance',
                (datetime.now(timezone.utc).isoformat(), bk),
            )
            conn.commit()

    def _risk_state(self) -> RiskState:
        with _connect() as conn:
            open_count = conn.execute(
                "SELECT COUNT(*) AS n FROM bets WHERE status = 'open'"
            ).fetchone()['n']
            open_stake = conn.execute(
                "SELECT IFNULL(SUM(stake), 0) AS s FROM bets WHERE status = 'open'"
            ).fetchone()['s']
            day_pnl = self._day_pnl(conn)
        return RiskState(
            bankroll=self.bankroll()['balance'],
            open_bets_count=open_count,
            open_bets_stake=float(open_stake),
            day_pnl=day_pnl,
            paused=bool(self._settings.get('paused')),
        )

    def _risk_limits(self) -> RiskLimits:
        s = self._settings
        return RiskLimits(
            min_bankroll=float(s['min_bankroll']),
            max_bet_pct=float(s['max_bet_pct']),
            daily_loss_pct=float(s['daily_loss_pct']),
            max_concurrent=int(s['max_concurrent']),
            max_total_exposure_pct=float(s['max_total_exposure_pct']),
        )

    def _day_pnl(self, conn: sqlite3.Connection) -> float:
        row = conn.execute(
            "SELECT IFNULL(SUM(payout), 0) AS p FROM bets "
            "WHERE status IN ('won','lost','push') AND settled_at >= ?",
            (self._local_midnight_iso(),),
        ).fetchone()
        return float(row['p'])

    @staticmethod
    def _local_midnight_iso() -> str:
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.astimezone(timezone.utc).isoformat()


# ── periodic scan loop ──────────────────────────────────────────────────────

async def scan_loop(server: HermesServer) -> None:
    interval = int(os.getenv('SCAN_INTERVAL_SECONDS', '300') or 300)
    while True:
        try:
            if not server.settings().get('paused'):
                await server.scan()
        except Exception as exc:
            print(f'[scan_loop] {exc}')
        await asyncio.sleep(interval)
