"""Elo-based outcome prediction.

The simplest defensible model: each team carries a rating, and the
predicted home-team win probability for a matchup is a logistic
function of the rating delta plus a home-court bump.

Ratings persist in `state.json` next to the database and are updated
when bets settle (see `server.update_ratings`). New teams start at the
sport's default rating.

This is intentionally simple. A real production model would consume
roster availability, pace, rest days, weather, etc. — the point here is
that the value engine has SOMETHING to compare bookmaker prices against,
shaped like a real prediction pipeline.
"""
from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass

# Different sports have different rating dispersions; these home-court
# advantages were eyeballed from public Elo references.
_HOME_BOOST: dict[str, float] = {
    'NFL':   55,
    'NBA':   90,
    'MLB':   25,
    'NHL':   45,
    'NCAAF': 65,
    'NCAAB': 105,
    'EPL':   60,
}

_SPORT_SCALE: dict[str, float] = {
    'NFL':   400.0,
    'NBA':   400.0,
    'MLB':   600.0,   # baseball is more random — flatter curve
    'NHL':   500.0,
    'NCAAF': 400.0,
    'NCAAB': 400.0,
    'EPL':   400.0,
}

_DEFAULT_RATING = 1500.0
_K = 24.0


@dataclass
class Prediction:
    home_prob: float
    away_prob: float
    home_rating: float
    away_rating: float


class PredictionEngine:
    """Thread-safe per-team Elo store with JSON persistence."""

    def __init__(self, state_path: str):
        self.state_path = state_path
        self._lock = threading.Lock()
        self._ratings: dict[str, dict[str, float]] = {}  # sport -> team -> rating
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    self._ratings = json.load(f).get('ratings', {})
            except Exception:
                self._ratings = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.state_path) or '.', exist_ok=True)
        tmp = self.state_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'ratings': self._ratings}, f, indent=2)
        os.replace(tmp, self.state_path)

    def rating(self, sport: str, team: str) -> float:
        return self._ratings.get(sport, {}).get(team, _DEFAULT_RATING)

    def predict(self, sport: str, home: str, away: str) -> Prediction:
        with self._lock:
            r_home = self.rating(sport, home)
            r_away = self.rating(sport, away)
            scale = _SPORT_SCALE.get(sport, 400.0)
            delta = (r_home + _HOME_BOOST.get(sport, 50)) - r_away
            p_home = 1.0 / (1.0 + math.pow(10.0, -delta / scale))
            return Prediction(p_home, 1.0 - p_home, r_home, r_away)

    def update_after_result(self, sport: str, home: str, away: str, home_won: bool) -> None:
        """Standard Elo update. Call after a bet settles to keep ratings live."""
        with self._lock:
            r_home = self.rating(sport, home)
            r_away = self.rating(sport, away)
            scale = _SPORT_SCALE.get(sport, 400.0)
            expected_home = 1.0 / (1.0 + math.pow(10.0, -(r_home - r_away) / scale))
            actual = 1.0 if home_won else 0.0
            r_home_new = r_home + _K * (actual - expected_home)
            r_away_new = r_away + _K * ((1.0 - actual) - (1.0 - expected_home))
            self._ratings.setdefault(sport, {})[home] = r_home_new
            self._ratings.setdefault(sport, {})[away] = r_away_new
            self._save()
