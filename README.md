# Hermes

> *Swift counsel for every wager.*

A model-driven sports betting app, modeled on the Proteus
(trading-bot-app) shape. A Python server runs the prediction engine,
finds value bets against bookmaker lines, and proposes wagers sized by
the Kelly criterion. A Flutter mobile app is the control surface.

```
odds API ──▶ server (FastAPI + SQLite)
             │  ├── prediction_engine (Elo)
             │  ├── value_engine      (Kelly sizing)
             │  └── risk_engine       (validate_bet — no override path)
             │
             └──REST──▶ Flutter app (Dashboard / Picks / History / Controls / Settings / Chat)
```

## Read this first — honest expectations

- **Paper mode is the default and the only mode shipped.** Hermes records
  proposed wagers in a local ledger; it does not place real bets with a
  sportsbook. Treating sports markets like a free ATM is how bankrolls die.
- **Edges are thin.** Sportsbook vig is ~4.5% on standard -110 lines. A
  model has to beat ~52.4% on point-spread bets just to break even before
  any commission. The value engine only surfaces bets above a configurable
  edge floor.
- **Bankroll discipline is non-negotiable.** Every bet runs through
  `risk_engine.validate_bet`. Block means block — no override path. See
  `server/risk_engine.py`. This mirrors Proteus's `validate_trade` rule.
- **Don't bet what you can't lose.** Variance in sports betting is brutal.
  The Kelly fraction in `value_engine` defaults to ¼-Kelly for a reason.

## Repository layout

| Path | Stack | Purpose |
|------|-------|---------|
| `lib/` | Flutter / Dart | Mobile app (control surface + dashboard) |
| `server/` | Python | API + prediction model + value detection + bot loop |
| `pubspec.yaml` | — | Flutter project manifest |

## Quick start

### Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # configure ODDS_API_KEY (or leave blank for mock data)
./start.sh                 # or: uvicorn api_server:app --host 0.0.0.0 --port 8000
```

The server is paper-mode and uses mocked odds data when `ODDS_API_KEY` is
unset, so you can run end-to-end with no credentials.

### App

```bash
flutter pub get
flutter run
```

Edit `lib/config.dart` to point at your backend before running on a device.

## Key files

| File | Purpose |
|------|---------|
| `lib/main.dart` | App entry, brand colors (`HermesColors`), `AuthGate`, `MainShell` |
| `lib/services/api_service.dart` | All backend calls |
| `lib/services/auth_service.dart` | Firebase Auth (email + Google) |
| `lib/screens/dashboard_screen.dart` | Bankroll, today's picks, P&L curve |
| `lib/screens/picks_screen.dart` | Current value bets from the model |
| `lib/screens/history_screen.dart` | Settled-bet ledger |
| `lib/screens/controls_screen.dart` | Bot pause, Kelly fraction, daily loss limit, sport filters |
| `lib/screens/settings_screen.dart` | Backend URL, account, sign-out |
| `lib/screens/chat_screen.dart` | AI assistant (BYOK Anthropic key) |
| `server/api_server.py` | FastAPI routes |
| `server/server.py` | Bot loop: fetch odds → predict → find value → size → validate → record |
| `server/odds_client.py` | The Odds API client (+ mock data) |
| `server/prediction_engine.py` | Elo-based outcome model |
| `server/value_engine.py` | Kelly criterion + edge floor |
| `server/risk_engine.py` | `validate_bet` — bankroll, daily loss, max bet, sanity |

## Safety rule (from `docs/research/sports-trading-app-refs.md`)

> Every order through a `validate_trade`-style gate, no override path, and
> no third-party repo touches a real key or funded wallet until it's been
> read end to end.

Hermes inherits this. `risk_engine.validate_bet` is the single gate. The
server never places real bets. If you wire a real sportsbook adapter in
the future, you place that adapter behind `validate_bet` — not around it.
