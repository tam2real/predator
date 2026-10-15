# Predator — Market Trading Skill

## What It Does

Hunts for good trades. Scans top 10 cryptos, finds support/resistance, scores setups, tracks positions, manages risk, delivers daily check-in.

**Core principle:** One check, one decision. Wake up, check once, decide once.

## Trigger

- "Market check"
- "Any good setups"
- "What's my P&L"
- "Open BTC long at $65,000"
- "Should I take this trade"

## Subfolders

| Folder | What It Does | Status |
|--------|-------------|--------|
| [market-scanner/](market-scanner/INDEX.md) | Top 10 crypto scan, S/R detection | BUILT |
| [support-resistance/](support-resistance/INDEX.md) | Key level detection | BUILT |
| [trade-signals/](trade-signals/INDEX.md) | Entry/exit signals | BUILT |
| [daily-checkin/](daily-checkin/INDEX.md) | Morning market briefing | BUILT |
| [risk-manager/](risk-manager/INDEX.md) | Prop firm rules and limits | BUILT |
| [agents/](agents/INDEX.md) | Trading agent scripts | COPIED |
| [skills/](skills/INDEX.md) | Trading skill references | COPIED |
| [dexview/](dexview/INDEX.md) | DexView integration | PLANNED |
| dashboard.html | Orb scanner dashboard UI | BUILT 2026-09-24 |

## What Was Copied

| File | Source | Purpose |
|------|--------|---------|
| market_monitor.py | D:/Sage Reborn/voice-os/ | Price tracking, alerts |
| trading_router.py | D:/Sage Reborn/voice-os/ | Multi-account routing |
| trader_agent.py | D:/Sage Reborn/voice-os/agents/ | Alpaca paper trading |
| sage_coin_agent.py | D:/Sage Reborn/voice-os/agents/ | Crypto trading agent |
| bitunix_agent.py | D:/Sage Reborn/voice-os/agents/ | Bitunix futures agent |
| analyst_agent.py | D:/Sage Reborn/voice-os/agents/ | Market analysis agent |
| breakout_prop_agent.py | D:/Sage Reborn/voice-os/agents/ | Breakout prop agent |
| trade-setup SKILL.md | D:/Sage Reborn/skills/ | Setup evaluation logic |
| paper-trader SKILL.md | D:/Sage Reborn/skills/ | Paper trading engine |

## What Was Created

| File | Purpose |
|------|---------|
| market-scanner/data/watchlist.json | Top 10 cryptos |
| risk-manager/data/risk-limits.json | BreakoutProp rules |
| daily-checkin/templates/morning-briefing.txt | Briefing template |
| trade-signals/data/signals.json | Signal history (empty) |
| support-resistance/data/levels.json | S/R levels (empty) |

## API Endpoints (14 total)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/market/scan | Scan top 10 cryptos (returns top 3) |
| GET | /api/market/setup/:symbol | Get setup for symbol + signal |
| GET | /api/market/price/:symbol | Get current price |
| GET | /api/market/levels/:symbol | Get support/resistance |
| GET | /api/market/chart/:symbol | Chart screenshot + S/R lines |
| POST | /api/gaze/position | Open position (via Gaze) |
| GET | /api/trade/positions | List open positions |
| GET | /api/trade/signal | Active signals |
| GET | /api/trade/signals | All signals |
| POST | /api/trade/close/:id | Close position (via Gaze) |
| GET | /api/risk/status | Risk status |
| POST | /api/risk/check | Check trade safety |
| GET | /api/checkin/daily | Daily briefing |
| GET | /api/checkin/weekly | Weekly review |

## External APIs Used

| API | Purpose |
|-----|---------|
| CoinGecko | Crypto prices, market cap |
| Kraken | BTC price fallback |
| Alpaca | Paper trading execution |
| Bitunix | Live futures (future) |

## TradingView Status

- Desktop app: INSTALLED at `C:/Users/odain/tradingview-local/`
- MCP server: NOT INSTALLED
- Webhooks: NOT CONFIGURED
- Integration: PLANNED

## Connection to Other Skills

| Skill | Relationship |
|-------|-------------|
| Great Sage | Analyzes screens, routes to Predator for market data |
| Gaze | Predator uses Gaze for P&L tracking; opens via POST /api/gaze/position |
| Stomach | Predator reads market data from Stomach |
| Shapeshifter | Can clone Predator for multi-account trading |
| Magic Sense | Predator provides data for morning recap |
| TradingView Bridge | Chart screenshots, watchlist, alerts via :9233 bridge + :3001 passthroughs |

## Sound Effects

| Event | Sound | File |
|-------|-------|------|
| Market scan starts | KOKU warning | warning.mp3 |
| Good setup found | Affirmative | affirmative.wav |
| Trade signal generated | NEURO | neuro.mp3 |
| Risk warning | KOKU | warning.mp3 |
| Briefing complete | Analysis complete | analysis-complete.wav |

## Status: BUILT (API + Dashboard)

- Market scanner: BUILT (`market-scanner/scanner.py` — CoinGecko batch + S/R + scoring)
- Signal engine: BUILT (`trade-signals/signal-engine.py` — structure-based signals)
- Risk checker: BUILT (`risk-manager/risk-check.py` — BreakoutProp rules)
- Daily briefing: BUILT (`daily-checkin/briefing.py` — fixed 500 crash, template formatting)
- HTTP endpoints: BUILT — 14 routes on standalone `:3001` (verified live 2026-09-24)
- TradingView bridge: BUILT — chart screenshot, watchlist, alerts via `:9233` + passthroughs
- Dashboard: BUILT — `predator/dashboard.html` (orb, scanner list, detail, chart, risk, trade panel, 30s refresh)
- Void registration: DONE
- Completion log: `01 - Daily Notes/2026/2026-09-24-predator-dashboard.md`
