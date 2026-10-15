# Predator — Market Trading Skill

Hunts for good trades. Scans the top cryptos, finds support/resistance, scores
setups, generates signals, manages risk, and delivers a daily briefing.
Core principle: one check, one decision.

## How it fits

```
Predator scans market -> scores setup -> signal -> opens position (via Gaze)
  ↓
Gaze tracks P&L live
  ↓
Trading City (3D) renders it all
```

## Layout

| Folder | Role |
|---|---|
| `agents/` | Trading agents: `trader_agent` (Alpaca paper), `bitunix_agent` (futures), `sage_coin_agent`, `analyst_agent`, `breakout_prop_agent` |
| `trade-signals/` | Signal engine + multi-account `trading_router.py` |
| `market-scanner/` | Top-10 crypto scan, S/R detection, scoring |
| `support-resistance/` | Key level detection (`data/levels.json`) |
| `risk-manager/` | Prop-firm rules and limits (`risk-check.py`, `data/risk-limits.json`) |
| `daily-checkin/` | Morning briefing generator |
| `skills/` | `paper-trader` and `trade-setup` skill references |
| `dexview/` | DexView integration (planned) |
| `dashboard.html` / `dexview-market.*` | UIs |

## Multi-account routing (the important part)

`trade-signals/trading_router.py` already routes per trade across account
types — this is the "12 towers, mixed accounts" model:

| Account | Type | Notes |
|---|---|---|
| `alpaca` | paper | $5k paper, buy-only crypto, no leverage |
| `bitunix` | live futures | leverage + shorts |
| `coinbase` | live | crypto + stocks |
| `kraken` | live | crypto |
| `breakout_prop_*` | manual prop | scalp / intermediate / long — Sage tracks setups, no API |

Anyone integrating plugs in their own platform the same way: add an entry to
`ACCOUNTS` in `trading_router.py` plus an agent in `agents/` — BitUnix,
Jupiter, any prop firm with an API. Keys always come from `.env`, never from
code.

## API (port :3001, 14 routes)

Market: `/api/market/scan`, `/api/market/setup/:symbol`, `/api/market/price/:symbol`,
`/api/market/levels/:symbol`, `/api/market/chart/:symbol`
Trades: `/api/trade/positions`, `/api/trade/signal`, `/api/trade/signals`, `POST /api/trade/close/:id`
(plus `POST /api/gaze/position` to open via Gaze)
Risk: `/api/risk/status`, `POST /api/risk/check`
Briefings: `/api/checkin/daily`, `/api/checkin/weekly`

## External data

CoinGecko (prices/market cap), Kraken (BTC fallback), Alpaca (paper),
Bitunix (live futures — future), TradingView bridge via `:9233` (planned).

## Keys (all via environment, never hardcoded)

Same set as Gaze: `ALPACA_*`, `BITUNIX_*`, `COINBASE_*`, `KRAKEN_*`.
No `.env` shipped — everyone brings their own.

## Notes

- Imported 2026-10-03 from the Windows "Sage Reborn" build; see `ORIGIN.md` and `BUILD-PLAN.md`.
- Cleanup 2026-10-15: removed `__pycache__/`. Code untouched.
- Name note: the zip was called "PREDATOR-CryptoCity" but the project is just **Predator** — "CryptoCity" was a custom label.
