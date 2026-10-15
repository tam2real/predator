# Predator — Market Trading Skill: Complete Build Plan

**Date:** 2026-09-24
**Status:** PLANNED — Architecture and dependencies documented
**References:** `SYSTEM-ARCHITECTURE.html`, `void/INDEX.md`, `FORGE-API.md`

---

## 1. What Predator Does

Predator is the crypto market hunting skill. It scans the top 10 cryptocurrencies, identifies support/resistance levels, scores trade signals, tracks open positions, and delivers a daily check-in briefing.

**Core principle:** One check, one decision. Wake up, check once, decide once. No monitoring, no stress.

---

## 2. What Already Exists

### Market Monitor
**Location:** `D:/Sage Reborn/voice-os/market_monitor.py` (12KB)

| Feature | Status |
|---------|--------|
| BTC price tracking | BUILT |
| Total market cap tracking | BUILT |
| 24h change detection | BUILT |
| Alert threshold (5%+) | BUILT |
| Background monitoring (20min intervals) | BUILT |
| CoinGecko + Kraken API fallback | BUILT |
| Alert queue for frontend | BUILT |

### Trading Router
**Location:** `D:/Sage Reborn/voice-os/trading_router.py` (8.5KB)

| Feature | Status |
|---------|--------|
| Multi-account routing | BUILT |
| Account list (Alpaca, Bitunix, Coinbase, Kraken, BreakoutProp x3) | BUILT |
| Symbol normalization | BUILT |
| Credential validation | BUILT |

### Trader Agent (Alpaca)
**Location:** `D:/Sage Reborn/voice-os/agents/trader_agent.py` (14KB)

| Feature | Status |
|---------|--------|
| Alpaca paper trading | BUILT |
| Buy/sell crypto | BUILT |
| Stop loss | BUILT |
| Symbol normalization | BUILT |
| Account guard (no creds = no trade) | BUILT |

### Trade Setup Review
**Location:** `D:/Sage Reborn/skills/trade-setup-review/trade-setup SKILL.md`

| Feature | Status |
|---------|--------|
| Structure evaluation | BUILT |
| Bias identification | BUILT |
| Entry logic review | BUILT |
| Invalidation detection | BUILT |
| Risk/reward calculation | BUILT |

### Paper Trader (ORB)
**Location:** `D:/Sage Reborn/voice-os/paper_trader.py` + `D:/Sage Reborn/skills/paper-trader/paper-trader SKILL.md`

| Feature | Status |
|---------|--------|
| $10K paper account | BUILT |
| 1% risk rule | BUILT |
| Position sizing formula | BUILT |
| Trade lifecycle (propose → approve → open → scale → close) | BUILT |
| Scale-in levels (3 auto-calculated) | BUILT |
| Vault logging | BUILT |
| Discord alerts | BUILT |
| ORB endpoints (8 routes) | BUILT |

**ORB Endpoints:**
```
GET  /paper/portfolio
GET  /paper/trades
GET  /paper/history
POST /paper/propose
POST /paper/approve
POST /paper/close
POST /paper/update
POST /paper/scale-in
```

### DexView (Jarvis)
**Location:** `C:/Users/odain/OneDrive/Desktop/Sage Memory Vault/02 - Agents/Jarvis/dexview/product_shell/dex-view.html` (988KB!)

| Feature | Status |
|---------|--------|
| Multi-mode dashboard | BUILT |
| Market mode (live prices) | BUILT |
| Map mode | BUILT |
| Desk mode | BUILT |
| Memory mode | BUILT |
| Atlas mode | BUILT |
| Skill mode | BUILT |
| Stream mode | BUILT |
| Build mode | BUILT |
| Lightweight charts | BUILT |
| Operator theming (13 operators) | BUILT |

### Market Monitor Data
**Location:** `D:/Sage Reborn/voice-os/data/`

| File | Contents |
|------|----------|
| `paper_portfolio.json` | Account balance, realized P&L |
| `paper_trades.json` | Open + closed trades |
| `paper_proposals.json` | Pending proposals |

---

## 3. What Predator Needs

### Subfolder Structure

```
predator/
├── INDEX.md                         ← Main index
├── market-scanner/                  ← Market scanning logic
│   ├── INDEX.md
│   ├── data/
│   │   └── watchlist.json           ← Top 10 cryptos
│   └── scanner.py                   ← Scan logic (wraps market_monitor.py)
├── support-resistance/              ← Key level detection
│   ├── INDEX.md
│   ├── data/
│   │   └── levels.json              ← Historical S/R levels
│   └── detector.py                  ← S/R detection algorithm
├── trade-signals/                   ← Entry/exit signals
│   ├── INDEX.md
│   ├── data/
│   │   └── signals.json             ← Signal history
│   └── signal-engine.py             ← Signal generation
├── daily-checkin/                   ← Morning briefing
│   ├── INDEX.md
│   ├── templates/
│   │   └── morning-briefing.txt     ← Template
│   └── briefing.py                  ← Briefing generator
└── risk-manager/                    ← Prop firm rules
    ├── INDEX.md
    ├── data/
    │   └── risk-limits.json         ← Configured limits
    └── risk-check.py                ← Risk validation
```

### API Endpoints (HTTP)

| Method | Endpoint | Description | Params | Returns |
|--------|----------|-------------|--------|---------|
| GET | /api/market/scan | Scan top 10 cryptos | — | { setups: [...], market: "bullish"|"bearish" } |
| GET | /api/market/setup/:symbol | Get setup for symbol | — | { symbol, structure, bias, entry, stop, target, confidence } |
| GET | /api/market/price/:symbol | Get current price | — | { symbol, price, change24h, source } |
| GET | /api/market/levels/:symbol | Get support/resistance | — | { symbol, support: [...], resistance: [...] } |
| POST | /api/trade/open | Open a position | symbol, direction, size, stop, target | { success, position } |
| GET | /api/trade/positions | List open positions | — | { positions: [...], totalRisk } |
| POST | /api/trade/close/:id | Close a position | reason | { success, pnl } |
| POST | /api/trade/scale-in/:id | Add to position | amount | { success, position } |
| GET | /api/trade/history | Trade history | — | { trades: [...], winRate, totalPnl } |
| GET | /api/trade/pnl/:id | Get P&L for position | — | { position, pnl, pnlPct, rMultiple } |
| GET | /api/risk/status | Get risk status | — | { dailyUsed, dailyRemaining, totalUsed, totalRemaining } |
| POST | /api/risk/check | Check if trade is safe | symbol, direction, size, stop | { safe, reason, riskAmount } |
| GET | /api/checkin/daily | Get daily briefing | — | { overview, setups, positions, risk } |
| GET | /api/checkin/weekly | Get weekly review | — | { summary, winners, losers, lessons } |

### External APIs Used

| API | Purpose | Used In |
|-----|---------|---------|
| CoinGecko | Crypto prices, market cap | market-scanner, support-resistance |
| Kraken | BTC price fallback | market-scanner |
| Alpaca | Paper trading execution | trade-signals |
| Bitunix | Live futures (future) | trade-signals |
| TradingView | Charts (HTML) | DexView market mode |

---

## 4. Wiring Plan

### Step 1: Market Scanner
```
market_monitor.py (existing)
  ↓
scanner.py (new wrapper)
  ├── Calls market_monitor for prices
  ├── Identifies support/resistance
  ├── Scores each setup 1-10
  └── Returns top 3 setups
```

### Step 2: Trade Signals
```
trade-setup-review SKILL.md (existing logic)
  ↓
signal-engine.py (new)
  ├── Analyzes market structure
  ├── Confirms with volume
  ├── Calculates risk/reward
  └── Generates signal with confidence
```

### Step 3: Daily Check-In
```
market_monitor.py + trade-signals + risk-manager
  ↓
briefing.py (new)
  ├── Pulls market overview
  ├── Lists open positions
  ├── Checks risk status
  └── Returns full briefing
```

### Step 4: Risk Manager
```
trading_router.py (account info)
  ↓
risk-check.py (new)
  ├── Validates against daily limit
  ├── Validates against total drawdown
  ├── Calculates position size
  └── Returns safe/unsafe + reason
```

---

## 5. Sound Effects Integration

| Event | Sound | File |
|-------|-------|------|
| Market scan starts | KOKU warning | warning.mp3 |
| Good setup found | Affirmative | affirmative.wav |
| Trade signal generated | NEURO | neuro.mp3 |
| Risk warning | KOKU | warning.mp3 |
| Briefing complete | Analysis complete | analysis-complete.wav |
| Position opened | NEURO | neuro.mp3 |
| Position closed | NEURO OFF | neurooff.mp3 |

---

## 6. Automation (Phase 3 — Later)

| Trigger | Schedule | What Runs |
|---------|----------|-----------|
| Daily check-in | 8:00 AM | briefing.py |
| Market scan | Every 4 hours | scanner.py |
| Position polling | Every 5 seconds | pnl-calculator.py |
| Risk check | Every 30 min | risk-check.py |

---

## 7. Connection to Void

All endpoints documented in `void/INDEX.md` under "Predator" section.

When Elfie needs to create a new trading skill:
1. Check Void for /api/market/*, /api/trade/*, /api/risk/*
2. Call the API to learn its format
3. Forge a new skill based on the API
4. Register the new skill in Void

---

## 8. Build Priority

1. **Market Scanner** — Wrap market_monitor.py, add S/R detection, score setups
2. **Trade Signals** — Build signal-engine.py from trade-setup-review logic
3. **Risk Manager** — Build risk-check.py from BreakoutProp rules
4. **Daily Check-In** — Build briefing.py from all three above
5. **API Endpoints** — Expose all as HTTP endpoints
6. **Void Registration** — Document all APIs in Void

---

## 9. What's Already Working

- market_monitor.py — live price tracking with alerts
- trading_router.py — multi-account routing
- trader_agent.py — Alpaca paper trading
- paper_trader.py — full ORB with 8 endpoints
- trade-setup-review — setup evaluation logic
- DexView — multi-mode dashboard with market view

## 10. What Needs Building

- scanner.py — wraps market_monitor with S/R + scoring
- signal-engine.py — generates trade signals
- risk-check.py — validates against prop firm rules
- briefing.py — morning market briefing
- HTTP endpoints — expose all as REST APIs
- Void registration — document all APIs

---

*This is the complete plan for Predator. Ready for OpenCode implementation.*
