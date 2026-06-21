"""Value detection and stake sizing.

A bet has positive expected value when the model's probability exceeds
the bookmaker's vig-adjusted implied probability by enough to beat the
edge floor. Stakes are sized by fractional Kelly.

`find_value_bets` consumes markets + predictions and returns the bets
worth proposing to the user. It does NOT actually place bets — that
goes through `risk_engine.validate_bet` first and is recorded by the
server.
"""
from __future__ import annotations

from dataclasses import dataclass

from odds_client import (
    Market,
    american_to_decimal,
    american_to_implied_prob,
    remove_vig_two_way,
)
from prediction_engine import Prediction


@dataclass
class ValueBet:
    """A proposed wager — what the value engine surfaces to the user."""
    sport: str
    matchup: str
    book: str
    selection: str          # team name being bet on
    side: str               # 'home' or 'away'
    event_id: str
    commences_at: str
    american_odds: int
    decimal_odds: float
    model_prob: float       # model's probability that this side wins
    market_prob: float      # vig-removed bookmaker probability
    edge: float             # model_prob - market_prob (de-vigged)
    expected_value: float   # per $1 stake
    stake: float            # dollars, sized by fractional Kelly + caps


def find_value_bets(
    markets: list[Market],
    predictions: dict[str, Prediction],   # keyed by event_id
    *,
    bankroll: float,
    min_edge: float,
    kelly_fraction: float,
    max_bet_pct: float,
) -> list[ValueBet]:
    """Scan all markets for a side with positive de-vigged edge over the floor.

    For each market we compute the bookmaker's implied probability on both
    sides, strip the overround, and compare to the model's prediction.
    Whichever side has more edge gets surfaced (at most one bet per market).
    """
    out: list[ValueBet] = []
    for m in markets:
        pred = predictions.get(m.event_id)
        if pred is None:
            continue

        # De-vig the bookmaker's market by normalizing both sides.
        home_implied = american_to_implied_prob(m.home_american)
        away_implied = american_to_implied_prob(m.away_american)
        home_fair, away_fair = remove_vig_two_way(home_implied, away_implied)

        home_edge = pred.home_prob - home_fair
        away_edge = pred.away_prob - away_fair

        if home_edge >= away_edge and home_edge >= min_edge:
            bet = _build_bet(m, 'home', pred.home_prob, home_fair, home_edge,
                             bankroll=bankroll, kelly_fraction=kelly_fraction,
                             max_bet_pct=max_bet_pct)
            if bet is not None:
                out.append(bet)
        elif away_edge >= min_edge:
            bet = _build_bet(m, 'away', pred.away_prob, away_fair, away_edge,
                             bankroll=bankroll, kelly_fraction=kelly_fraction,
                             max_bet_pct=max_bet_pct)
            if bet is not None:
                out.append(bet)

    out.sort(key=lambda b: b.edge, reverse=True)
    return out


def _build_bet(market: Market, side: str, model_p: float, market_p: float,
               edge: float, *, bankroll: float, kelly_fraction: float,
               max_bet_pct: float) -> ValueBet | None:
    american = market.home_american if side == 'home' else market.away_american
    decimal_odds = american_to_decimal(american)
    selection = market.home_team if side == 'home' else market.away_team

    stake = _kelly_stake(
        bankroll=bankroll,
        prob=model_p,
        decimal_odds=decimal_odds,
        kelly_fraction=kelly_fraction,
        max_bet_pct=max_bet_pct,
    )
    if stake <= 0:
        return None

    ev_per_dollar = model_p * (decimal_odds - 1.0) - (1.0 - model_p)
    return ValueBet(
        sport=market.sport,
        matchup=market.matchup,
        book=market.book,
        selection=selection,
        side=side,
        event_id=market.event_id,
        commences_at=market.commences_at,
        american_odds=american,
        decimal_odds=decimal_odds,
        model_prob=model_p,
        market_prob=market_p,
        edge=edge,
        expected_value=ev_per_dollar,
        stake=round(stake, 2),
    )


def _kelly_stake(*, bankroll: float, prob: float, decimal_odds: float,
                 kelly_fraction: float, max_bet_pct: float) -> float:
    """Fractional Kelly. Returns 0 when the formula says don't bet."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob
    edge_per_dollar = prob - q / b
    if edge_per_dollar <= 0:
        return 0.0
    fraction = (edge_per_dollar / b) * kelly_fraction
    fraction = min(fraction, max_bet_pct)
    return max(0.0, bankroll * fraction)
