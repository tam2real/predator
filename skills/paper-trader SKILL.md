---
name: paper-trader
description: >
  Complete reference for TAM2REAL's paper trading engine. Covers the $10k
  account, 1% risk rule, position sizing formula, proposal → approval → open
  → scale-in → close lifecycle, ORB endpoints, and data file locations.
  Load before ANY paper trading work — adding features, debugging trades,
  reading P&L, resetting the account, or changing risk rules.
  Triggers on: "paper trade", "paper trading", "open a trade", "close a trade",
  "paper portfolio", "trade proposal", "scale in", "P&L", "paper_trader.py",
  "paper_trades.json", "1% risk", "position sizing", "stop loss", "take profit",
  "trade not opening", "trade not closing", "paper account balance".
---

# Paper Trader — TAM2REAL Engine

$10,000 paper account. 1% risk per trade. Every trade goes through approval.

---

## Account Rules

```
Starting capital:   $10,000
Risk per trade:     1% = $100 max risk
Default stop:       4% from entry
Default target:     12% from entry (3R minimum)
Leverage:           None — shares only
```

---

## Trade Lifecycle

```
propose → (agent or MC sends proposal) → pending approval
approve → /paper/approve  → opens position at fill price
update  → /paper/update   → updates current price + trailing stop
scale-in→ /paper/scale-in → adds to position at new level
close   → /paper/close    → exits trade, logs P&L to vault + Discord
```

---

## Data Files

| File | Contains |
|---|---|
| `voice-os/data/paper_portfolio.json` | Account balance, realized P&L, trade count |
| `voice-os/data/paper_trades.json` | All open + closed trades |
| `voice-os/data/paper_proposals.json` | Pending proposals waiting for approval |

---

## ORB Endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `GET /paper/portfolio` | GET | Account balance, equity, realized P&L |
| `GET /paper/trades` | GET | All open trades |
| `GET /paper/history` | GET | Closed trades |
| `POST /paper/propose` | POST | Create new proposal |
| `POST /paper/approve` | POST | Approve + open a proposal |
| `POST /paper/close` | POST | Close an open trade |
| `POST /paper/update` | POST | Update price + trailing stop |
| `POST /paper/scale-in` | POST | Add to existing position |

---

## Position Sizing Formula

```python
risk_dollars = capital * risk_pct          # $10,000 * 0.01 = $100
stop_distance = abs(entry - stop_loss)
shares = risk_dollars / stop_distance

# Example: AAPL entry $175, stop $168
# stop_distance = $7
# shares = $100 / $7 = 14.28 shares
# position_size = 14.28 * $175 = $2,499
```

---

## Scale-In Levels (auto-calculated)

When a trade is proposed, 3 scale-in levels are pre-calculated:
```
Level 1: entry + 1x stop_distance — add 50% of original shares
Level 2: entry + 2x stop_distance — add 25%
Level 3: entry + 3x stop_distance — add 12.5%
```
Each scale-in lowers the average entry and increases position size.

---

## Vault Logging

Every open and close automatically logs to Obsidian daily note via
`append_to_connected_vaults()`. Format:

**Open:**
```
📈 PAPER TRADE OPEN — LONG AAPL
Entry: $175.00 | Shares: 14.28 | Size: $2,499
Stop: $168.00 (-4.0%) | Target: $196.00 (+12.0%)
Risk: $100.00 | R:R: 3.00R | ID: `pt-abc12345`
```

**Close:**
```
✅ PAPER TRADE CLOSE — LONG AAPL [WIN]
Exit: $196.00 | P&L: +$299.00 | R-multiple: +2.99R
Reason: take_profit | ID: `pt-abc12345`
```

---

## CLI Commands (direct script use)

```bat
python paper_trader.py portfolio
python paper_trader.py trades
python paper_trader.py propose AAPL 175.50 LONG
python paper_trader.py propose BTC-USD 65000 LONG 0.04 0.12
python paper_trader.py open pt-abc12345 [fill_price]
python paper_trader.py close pt-abc12345 180.00 take_profit
python paper_trader.py scale-in pt-abc12345 1 172.00
```

---

## Reset Account

To reset to $10,000 fresh:
```python
# Delete paper_portfolio.json and paper_trades.json
# ORB will re-seed on next request
import os
os.remove("voice-os/data/paper_portfolio.json")
os.remove("voice-os/data/paper_trades.json")
```

---

## Common Issues

| Problem | Fix |
|---|---|
| Trade won't open | Check proposal exists in paper_proposals.json, status = "pending" |
| P&L not updating | POST to `/paper/update` with current price |
| Vault not logging | Check OBSIDIAN_VAULT in .env — see `obsidian-logging` skill |
| Account balance wrong | Check paper_portfolio.json — realized_pnl accumulates per close |
| Discord alert missing | Check DISCORD_ALERTS_CHANNEL_ID in .env — see `discord-bot-commands` skill |

---

## Scope

`voice-os/paper_trader.py` + `sage_orb.py` endpoints + `data/paper_*.json` files.

---
**Back to:** [[../../skills/Skills District|Skills District]] | [[../../HOME|HOME]]
