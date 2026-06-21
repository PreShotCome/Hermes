"""The Odds API client + mock fallback.

Live mode: https://the-odds-api.com/liveapi/guides/v4/
Mock mode (default when ODDS_API_KEY is unset): generates a small set of
deterministic-ish synthetic markets so the rest of the system can run
end-to-end with zero credentials.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

import httpx


ODDS_API_BASE = 'https://api.the-odds-api.com/v4'

# Map our short sport codes to The Odds API's sport_keys.
SPORT_KEY = {
    'NFL':   'americanfootball_nfl',
    'NCAAF': 'americanfootball_ncaaf',
    'NBA':   'basketball_nba',
    'NCAAB': 'basketball_ncaab',
    'MLB':   'baseball_mlb',
    'NHL':   'icehockey_nhl',
    'EPL':   'soccer_epl',
}


@dataclass
class Market:
    """A single moneyline market for one event."""
    event_id: str
    sport: str            # short code (NFL, NBA, ...)
    matchup: str          # 'Lakers @ Celtics'
    home_team: str
    away_team: str
    commences_at: str     # ISO8601
    book: str             # 'mock' or 'fanduel' etc.
    home_american: int    # american odds for home win
    away_american: int


def american_to_decimal(american: int) -> float:
    if american > 0:
        return 1.0 + american / 100.0
    return 1.0 + 100.0 / abs(american)


def american_to_implied_prob(american: int) -> float:
    """Bookmaker implied probability INCLUDING vig."""
    if american > 0:
        return 100.0 / (american + 100.0)
    return abs(american) / (abs(american) + 100.0)


def remove_vig_two_way(p_home: float, p_away: float) -> tuple[float, float]:
    """Normalize a two-outcome market to remove the bookmaker's overround."""
    total = p_home + p_away
    if total <= 0:
        return 0.5, 0.5
    return p_home / total, p_away / total


def decimal_to_american(dec: float) -> int:
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100.0 / (dec - 1.0)))


class OddsClient:
    def __init__(self, api_key: str | None = None, *, timeout: float = 10.0):
        self.api_key = api_key or os.getenv('ODDS_API_KEY') or ''
        self.timeout = timeout
        self.live = bool(self.api_key)

    async def fetch_markets(self, sports: Iterable[str]) -> list[Market]:
        sports = [s for s in sports if s in SPORT_KEY]
        if not sports:
            return []
        if not self.live:
            return _mock_markets(sports)
        out: list[Market] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for sport in sports:
                try:
                    out.extend(await self._fetch_one(client, sport))
                except Exception as exc:
                    print(f'[odds] {sport}: {exc}')
        return out

    async def _fetch_one(self, client: httpx.AsyncClient, sport: str) -> list[Market]:
        key = SPORT_KEY[sport]
        url = f'{ODDS_API_BASE}/sports/{key}/odds'
        r = await client.get(url, params={
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h',
            'oddsFormat': 'american',
        })
        r.raise_for_status()
        events = r.json()
        markets: list[Market] = []
        for ev in events:
            home = ev.get('home_team', '')
            away = ev.get('away_team', '')
            commences = ev.get('commence_time', '')
            for book in ev.get('bookmakers', []):
                book_key = book.get('key', '')
                h2h = next((m for m in book.get('markets', []) if m.get('key') == 'h2h'), None)
                if not h2h:
                    continue
                home_odds = next((o for o in h2h.get('outcomes', []) if o.get('name') == home), None)
                away_odds = next((o for o in h2h.get('outcomes', []) if o.get('name') == away), None)
                if not (home_odds and away_odds):
                    continue
                markets.append(Market(
                    event_id=str(ev.get('id', '')),
                    sport=sport,
                    matchup=f'{away} @ {home}',
                    home_team=home,
                    away_team=away,
                    commences_at=commences,
                    book=book_key,
                    home_american=int(home_odds.get('price', 0)),
                    away_american=int(away_odds.get('price', 0)),
                ))
        return markets


# ── Mock data ───────────────────────────────────────────────────────────────

_MOCK_TEAMS: dict[str, list[str]] = {
    'NFL':   ['49ers', 'Chiefs', 'Eagles', 'Ravens', 'Bills', 'Cowboys', 'Lions', 'Dolphins'],
    'NBA':   ['Celtics', 'Nuggets', 'Bucks', 'Lakers', 'Warriors', 'Heat', 'Knicks', 'Suns'],
    'MLB':   ['Yankees', 'Dodgers', 'Astros', 'Braves', 'Phillies', 'Mets', 'Padres', 'Cubs'],
    'NHL':   ['Rangers', 'Oilers', 'Maple Leafs', 'Avalanche', 'Bruins', 'Panthers'],
    'NCAAF': ['Georgia', 'Michigan', 'Alabama', 'Texas', 'Oregon', 'Ohio State'],
    'NCAAB': ['Duke', 'UConn', 'Kansas', 'Houston', 'Purdue', 'Tennessee'],
    'EPL':   ['Arsenal', 'Man City', 'Liverpool', 'Spurs', 'Chelsea', 'Newcastle'],
}

_MOCK_BOOKS = ['draftkings', 'fanduel', 'mgm', 'caesars']


def _mock_markets(sports: list[str]) -> list[Market]:
    """Generate a handful of plausible markets. Seeded by the current 10-min
    bucket so consecutive scans are stable but the slate evolves over time."""
    bucket = int(time.time() // 600)
    rng = random.Random(bucket)
    markets: list[Market] = []
    for sport in sports:
        teams = _MOCK_TEAMS.get(sport, [])
        if len(teams) < 2:
            continue
        rng.shuffle(teams)
        n_games = min(3, len(teams) // 2)
        for i in range(n_games):
            home = teams[2 * i]
            away = teams[2 * i + 1]
            # underlying "true" home win probability
            true_p = 0.35 + rng.random() * 0.30
            home_american = _prob_to_american(true_p + rng.uniform(-0.04, 0.04))
            away_american = _prob_to_american(1 - true_p + rng.uniform(-0.04, 0.04))
            # Apply a small overround so a value bet is occasionally visible.
            home_american = _bump_juice(home_american, rng.uniform(0.01, 0.04))
            away_american = _bump_juice(away_american, rng.uniform(0.01, 0.04))
            commences = (datetime.now(timezone.utc) + timedelta(hours=rng.randint(2, 36))).isoformat()
            book = rng.choice(_MOCK_BOOKS)
            markets.append(Market(
                event_id=f'mock_{sport}_{bucket}_{i}',
                sport=sport,
                matchup=f'{away} @ {home}',
                home_team=home,
                away_team=away,
                commences_at=commences,
                book=book,
                home_american=home_american,
                away_american=away_american,
            ))
    return markets


def _prob_to_american(p: float) -> int:
    p = max(0.02, min(0.98, p))
    return decimal_to_american(1.0 / p)


def _bump_juice(american: int, juice: float) -> int:
    """Push the implied probability up by `juice` (vig) and return new line."""
    p = american_to_implied_prob(american)
    p = min(0.98, p + juice)
    return decimal_to_american(1.0 / p)
