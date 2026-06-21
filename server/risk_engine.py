"""The single gate every bet goes through.

Mirrors Proteus's `validate_trade` rule from the bot playbook:

>  Every order through a validate-style gate. Block = block. No override path.

If `validate_bet` returns a `RiskBlock`, the bet does NOT get placed.
The server (`api_server.py`) never bypasses this — there is no
override flag, no force-place endpoint, no "trusted caller" exemption.
If you wire up a real sportsbook adapter someday, you place it BEHIND
this gate, not around it.
"""
from __future__ import annotations

from dataclasses import dataclass

from value_engine import ValueBet


@dataclass
class RiskState:
    """Snapshot of bankroll & daily P&L the gate needs to make a call."""
    bankroll: float
    open_bets_count: int
    open_bets_stake: float       # total dollars on open bets right now
    day_pnl: float               # settled P&L since local midnight
    paused: bool


@dataclass
class RiskLimits:
    min_bankroll: float          # refuse to bet below this floor
    max_bet_pct: float           # hard cap per bet, % of bankroll
    daily_loss_pct: float        # halt new bets after this drawdown today
    max_concurrent: int          # don't let exposure runaway
    max_total_exposure_pct: float  # combined open-stake cap


@dataclass
class RiskBlock:
    """Reason a bet was rejected. Never None when validate_bet returns one."""
    code: str
    reason: str


def validate_bet(bet: ValueBet, state: RiskState, limits: RiskLimits) -> RiskBlock | None:
    """Return None to allow, or a RiskBlock to reject. No override path."""

    if state.paused:
        return RiskBlock('paused', 'Engine is paused.')

    if state.bankroll < limits.min_bankroll:
        return RiskBlock(
            'min_bankroll',
            f'Bankroll ${state.bankroll:.2f} below floor ${limits.min_bankroll:.2f}.',
        )

    if bet.stake <= 0:
        return RiskBlock('zero_stake', 'Stake is zero or negative.')

    cap = state.bankroll * limits.max_bet_pct
    if bet.stake > cap + 1e-6:
        return RiskBlock(
            'max_bet_pct',
            f'Stake ${bet.stake:.2f} exceeds per-bet cap ${cap:.2f}.',
        )

    daily_loss_cap = -abs(state.bankroll * limits.daily_loss_pct)
    if state.day_pnl <= daily_loss_cap:
        return RiskBlock(
            'daily_loss_stop',
            f'Daily P&L ${state.day_pnl:.2f} hit stop ${daily_loss_cap:.2f}.',
        )

    if state.open_bets_count >= limits.max_concurrent:
        return RiskBlock(
            'max_concurrent',
            f'Already at concurrent-bet limit ({limits.max_concurrent}).',
        )

    total_exposure_cap = state.bankroll * limits.max_total_exposure_pct
    projected_exposure = state.open_bets_stake + bet.stake
    if projected_exposure > total_exposure_cap + 1e-6:
        return RiskBlock(
            'max_total_exposure',
            f'Total stake ${projected_exposure:.2f} exceeds exposure cap ${total_exposure_cap:.2f}.',
        )

    if bet.edge < 0:
        return RiskBlock('negative_edge', 'Bet has no positive edge.')

    if bet.model_prob <= 0.0 or bet.model_prob >= 1.0:
        return RiskBlock('bad_prob', f'Model probability {bet.model_prob} out of (0,1).')

    return None
