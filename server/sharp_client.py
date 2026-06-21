"""SharpAPI client + odds math + market types.

Free tier (12 req/min) gives us `/api/v1/odds` and `/api/v1/events`. The
EV / Kelly / no-vig endpoints are Pro-gated, so we do that math locally:
fetch raw odds from FanDuel and Pinnacle, de-vig Pinnacle's two-sided
market to get the fair probability, and let `value_engine` do the
edge + Kelly math.

When SHARP_API_KEY is unset, falls back to deterministic mock data so
the rest of the system runs end-to-end with no credentials.

Docs: https://docs.sharpapi.io/en/
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import httpx


SHARP_BASE   = 'https://api.sharpapi.io/api/v1'
FANDUEL_KEY  = 'fanduel'
PINNACLE_KEY = 'pinnacle'

# Map our sport codes to SharpAPI's league identifiers.
LEAGUE_KEY: dict[str, str] = {
    'NFL':   'nfl',
    'NCAAF': 'ncaaf',
    'NBA':   'nba',
    'NCAAB': 'ncaab',
    'MLB':   'mlb',
    'NHL':   'nhl',
    'EPL':   'epl',
}


# ── odds math ───────────────────────────────────────────────────────────────

def american_to_decimal(american: int) -> float:
    if american > 0:
        return 1.0 + american / 100.0
    return 1.0 + 100.0 / abs(american)


def american_to_implied_prob(american: int) -> float:
    """Implied probability INCLUDING vig."""
    if american > 0:
        return 100.0 / (american + 100.0)
    return abs(american) / (abs(american) + 100.0)


def decimal_to_american(dec: float) -> int:
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100.0 / (dec - 1.0)))


def remove_vig_two_way(p_home: float, p_away: float) -> tuple[float, float]:
    """Strip the bookmaker's overround from a two-outcome market."""
    total = p_home + p_away
    if total <= 0:
        return 0.5, 0.5
    return p_home / total, p_away / total


# ── data shapes ─────────────────────────────────────────────────────────────

@dataclass
class Market:
    """A single moneyline market at one sportsbook for one event."""
    event_id: str
    sport: str            # short code (NFL, NBA, ...)
    matchup: str          # 'Lakers @ Celtics'
    home_team: str
    away_team: str
    commences_at: str     # ISO8601
    book: str             # 'fanduel' or 'pinnacle'
    home_american: int
    away_american: int


@dataclass
class PairedMarket:
    """FanDuel posted line paired with Pinnacle reference for the same event.

    Pinnacle is the sharp anchor — its de-vigged line is our `model_prob`.
    FanDuel is the book we'd actually place at.
    """
    fanduel: Market
    pinnacle: Market

    @property
    def event_id(self) -> str: return self.fanduel.event_id

    def pinnacle_fair(self) -> tuple[float, float]:
        """Returns (home_fair_prob, away_fair_prob) — de-vigged Pinnacle."""
        p_home_raw = american_to_implied_prob(self.pinnacle.home_american)
        p_away_raw = american_to_implied_prob(self.pinnacle.away_american)
        return remove_vig_two_way(p_home_raw, p_away_raw)


# ── client ──────────────────────────────────────────────────────────────────

class SharpClient:
    def __init__(self, api_key: str | None = None, *, timeout: float = 10.0):
        self.api_key = api_key or os.getenv('SHARP_API_KEY') or ''
        self.timeout = timeout
        self.live = bool(self.api_key)

    async def fetch_paired_markets(self, sports: Iterable[str]) -> list[PairedMarket]:
        """Return one PairedMarket per event where both FanDuel and Pinnacle
        have a moneyline posted. Events with only one of the two are dropped
        (we can't compute fair price without the sharp anchor)."""
        leagues = [LEAGUE_KEY[s] for s in sports if s in LEAGUE_KEY]
        if not leagues:
            return []
        if not self.live:
            return _mock_paired(leagues)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                rows = await self._fetch_odds(client, leagues)
            except Exception as exc:
                print(f'[sharp] fetch failed: {exc}')
                return []

        return _pair_by_event(rows)

    async def _fetch_odds(self, client: httpx.AsyncClient,
                          leagues: list[str]) -> list[dict]:
        """One call covers all leagues + both books — well within free tier."""
        params = {
            'league':     ','.join(leagues),
            'sportsbook': f'{FANDUEL_KEY},{PINNACLE_KEY}',
            'market':     'moneyline',
            'limit':      200,
        }
        r = await client.get(
            f'{SHARP_BASE}/odds',
            params=params,
            headers={'X-API-Key': self.api_key},
        )
        r.raise_for_status()
        payload = r.json()
        return payload.get('data', []) or []


def _pair_by_event(rows: list[dict]) -> list[PairedMarket]:
    """Bucket /odds rows by (event_id, book), then collapse to PairedMarkets.

    SharpAPI returns one row per (event, book, selection). We need both
    sides at each book for de-vigging, and both books to pair them.
    """
    by_event: dict[str, dict[str, dict[str, dict]]] = {}
    for row in rows:
        event_id = row.get('event_id') or ''
        book     = (row.get('sportsbook') or '').lower()
        side     = (row.get('selection_type') or '').lower()
        if not (event_id and book and side in ('home', 'away')):
            continue
        by_event.setdefault(event_id, {}).setdefault(book, {})[side] = row

    paired: list[PairedMarket] = []
    for event_id, books in by_event.items():
        fd = books.get(FANDUEL_KEY,  {})
        pn = books.get(PINNACLE_KEY, {})
        if not (fd.get('home') and fd.get('away') and pn.get('home') and pn.get('away')):
            continue
        # All four rows share the same event metadata; grab from the first.
        sample = fd['home']
        home_team = sample.get('home_team') or ''
        away_team = sample.get('away_team') or ''
        commences = sample.get('event_start_time') or ''
        league    = (sample.get('league') or '').upper()
        sport_code = league if league in LEAGUE_KEY else _sport_from_league(sample.get('league'))

        fanduel = Market(
            event_id=event_id, sport=sport_code,
            matchup=f'{away_team} @ {home_team}',
            home_team=home_team, away_team=away_team,
            commences_at=commences, book=FANDUEL_KEY,
            home_american=int(fd['home'].get('odds_american', 0)),
            away_american=int(fd['away'].get('odds_american', 0)),
        )
        pinnacle = Market(
            event_id=event_id, sport=sport_code,
            matchup=f'{away_team} @ {home_team}',
            home_team=home_team, away_team=away_team,
            commences_at=commences, book=PINNACLE_KEY,
            home_american=int(pn['home'].get('odds_american', 0)),
            away_american=int(pn['away'].get('odds_american', 0)),
        )
        paired.append(PairedMarket(fanduel=fanduel, pinnacle=pinnacle))
    return paired


def _sport_from_league(league: str | None) -> str:
    if not league:
        return ''
    inv = {v: k for k, v in LEAGUE_KEY.items()}
    return inv.get(league.lower(), league.upper())


# ── mock data ───────────────────────────────────────────────────────────────

_MOCK_TEAMS: dict[str, list[str]] = {
    'NFL':   ['49ers', 'Chiefs', 'Eagles', 'Ravens', 'Bills', 'Cowboys', 'Lions', 'Dolphins'],
    'NBA':   ['Celtics', 'Nuggets', 'Bucks', 'Lakers', 'Warriors', 'Heat', 'Knicks', 'Suns'],
    'MLB':   ['Yankees', 'Dodgers', 'Astros', 'Braves', 'Phillies', 'Mets', 'Padres', 'Cubs'],
    'NHL':   ['Rangers', 'Oilers', 'Maple Leafs', 'Avalanche', 'Bruins', 'Panthers'],
    'NCAAF': ['Georgia', 'Michigan', 'Alabama', 'Texas', 'Oregon', 'Ohio State'],
    'NCAAB': ['Duke', 'UConn', 'Kansas', 'Houston', 'Purdue', 'Tennessee'],
    'EPL':   ['Arsenal', 'Man City', 'Liverpool', 'Spurs', 'Chelsea', 'Newcastle'],
}


def _mock_paired(leagues: list[str]) -> list[PairedMarket]:
    """Synthetic FanDuel + Pinnacle pairs. Bucketed by 10-min so consecutive
    scans are stable but the slate evolves. Pinnacle gets a thin ~2% vig;
    FanDuel gets a wider ~5% with the home side occasionally over-juiced to
    create visible edges."""
    bucket = int(time.time() // 600)
    rng = random.Random(bucket)
    out: list[PairedMarket] = []
    sport_codes = {v: k for k, v in LEAGUE_KEY.items()}
    for league in leagues:
        sport = sport_codes.get(league, league.upper())
        teams = list(_MOCK_TEAMS.get(sport, []))
        if len(teams) < 2:
            continue
        rng.shuffle(teams)
        for i in range(min(3, len(teams) // 2)):
            home, away = teams[2*i], teams[2*i+1]
            true_p = 0.35 + rng.random() * 0.30
            pn_home = _juice(true_p,           rng.uniform(0.005, 0.015))
            pn_away = _juice(1 - true_p,       rng.uniform(0.005, 0.015))
            fd_home = _juice(true_p + rng.uniform(-0.03, 0.03), rng.uniform(0.015, 0.04))
            fd_away = _juice(1 - true_p + rng.uniform(-0.03, 0.03), rng.uniform(0.015, 0.04))
            commences = (datetime.now(timezone.utc) + timedelta(hours=rng.randint(2, 36))).isoformat()
            event_id  = f'mock_{league}_{bucket}_{i}'
            fanduel = Market(
                event_id=event_id, sport=sport,
                matchup=f'{away} @ {home}', home_team=home, away_team=away,
                commences_at=commences, book=FANDUEL_KEY,
                home_american=fd_home, away_american=fd_away,
            )
            pinnacle = Market(
                event_id=event_id, sport=sport,
                matchup=f'{away} @ {home}', home_team=home, away_team=away,
                commences_at=commences, book=PINNACLE_KEY,
                home_american=pn_home, away_american=pn_away,
            )
            out.append(PairedMarket(fanduel=fanduel, pinnacle=pinnacle))
    return out


def _juice(p: float, vig: float) -> int:
    p = max(0.02, min(0.98, p + vig))
    return decimal_to_american(1.0 / p)
