"""Value detection + Kelly sizing.

`sharp_client` supplies the inputs: FanDuel's posted moneyline paired
with Pinnacle's reference, which we treat as the sharp anchor (its
de-vigged probability IS our model probability). This module picks the
side with the larger edge and sizes a fractional-Kelly stake.

It does NOT place bets — proposed bets go through
`risk_engine.validate_bet` first, recorded by `server`.
"""
from __future__ import annotations

from dataclasses import dataclass

from sharp_client import (
    PairedMarket,
    american_to_decimal,
    american_to_implied_prob,
    remove_vig_two_way,
)


@dataclass
class ValueBet:
    """A proposed wager — what the value engine surfaces to the user."""
    sport: str
    matchup: str
    book: str               # always 'fanduel' for now
    selection: str
    side: str               # 'home' or 'away'
    event_id: str
    commences_at: str
    american_odds: int
    decimal_odds: float
    model_prob: float       # Pinnacle de-vigged fair probability
    market_prob: float      # FanDuel de-vigged implied probability
    edge: float             # model_prob - market_prob
    expected_value: float   # per $1 staked at FanDuel's posted line
    stake: float            # dollars, fractional-Kelly sized with caps


def find_value_bets(
    pairs: list[PairedMarket],
    *,
    bankroll: float,
    min_edge: float,
    kelly_fraction: float,
    max_bet_pct: float,
) -> list[ValueBet]:
    """For each event, pick the side where Pinnacle's fair price beats
    FanDuel's de-vigged implied by at least `min_edge`. Size by Kelly."""
    out: list[ValueBet] = []
    for pair in pairs:
        home_fair, away_fair = pair.pinnacle_fair()

        fd = pair.fanduel
        fd_home_implied = american_to_implied_prob(fd.home_american)
        fd_away_implied = american_to_implied_prob(fd.away_american)
        fd_home_fair, fd_away_fair = remove_vig_two_way(fd_home_implied, fd_away_implied)

        home_edge = home_fair - fd_home_fair
        away_edge = away_fair - fd_away_fair

        if home_edge >= away_edge and home_edge >= min_edge:
            bet = _build_bet(pair, 'home', home_fair, fd_home_fair, home_edge,
                             bankroll=bankroll, kelly_fraction=kelly_fraction,
                             max_bet_pct=max_bet_pct)
        elif away_edge >= min_edge:
            bet = _build_bet(pair, 'away', away_fair, fd_away_fair, away_edge,
                             bankroll=bankroll, kelly_fraction=kelly_fraction,
                             max_bet_pct=max_bet_pct)
        else:
            bet = None

        if bet is not None:
            out.append(bet)

    out.sort(key=lambda b: b.edge, reverse=True)
    return out


def _build_bet(pair: PairedMarket, side: str, model_p: float, market_p: float,
               edge: float, *, bankroll: float, kelly_fraction: float,
               max_bet_pct: float) -> ValueBet | None:
    fd = pair.fanduel
    american = fd.home_american if side == 'home' else fd.away_american
    decimal_odds = american_to_decimal(american)
    selection = fd.home_team if side == 'home' else fd.away_team

    stake = _kelly_stake(
        bankroll=bankroll, prob=model_p, decimal_odds=decimal_odds,
        kelly_fraction=kelly_fraction, max_bet_pct=max_bet_pct,
    )
    if stake <= 0:
        return None

    ev_per_dollar = model_p * (decimal_odds - 1.0) - (1.0 - model_p)
    return ValueBet(
        sport=fd.sport, matchup=fd.matchup, book=fd.book,
        selection=selection, side=side,
        event_id=fd.event_id, commences_at=fd.commences_at,
        american_odds=american, decimal_odds=decimal_odds,
        model_prob=model_p, market_prob=market_p,
        edge=edge, expected_value=ev_per_dollar,
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
