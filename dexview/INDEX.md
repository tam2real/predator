# DexView Integration — Predator

## What It Is

DexView is the multi-mode dashboard that already exists in the vault. Predator uses the **market mode** for live crypto charts and price data.

## Source Location

**Canonical:** `C:/Users/odain/OneDrive/Desktop/Sage Memory Vault/02 - Agents/Jarvis/dexview/product_shell/dex-view.html` (988KB)

**Modes:**
| Mode | Purpose |
|------|---------|
| market | Live crypto prices, charts, watchlist |
| map | Geographic view |
| desk | Desktop overview |
| memory | Memory/knowledge view |
| atlas | Atlas view |
| skill | Skill management |
| stream | Stream monitoring |
| build | Build/development view |

## What Predator Uses

- **Market mode** — Live prices, charts, watchlist
- **Lightweight Charts** — Charting library (already embedded in DexView)
- **Operator theming** — 13-operator color scheme

## Integration Plan

Predator's market scanner will:
1. Pull data from CoinGecko/Kraken APIs (via market_monitor.py)
2. Display in DexView market mode
3. Overlay support/resistance levels on charts
4. Show trade signals as chart annotations

## TradingView Desktop App

**Location:** `C:/Users/odain/tradingview-local/`

This is the TradingView desktop application (Electron/Chromium). It is NOT an MCP server. It is a standalone app.

**What it can do:**
- Display charts with indicators
- Set alerts with webhooks
- Draw trendlines and support/resistance

**What it cannot do (without MCP):**
- Send data to Predator automatically
- Receive signals from Predator
- Integrate with Elfie's tool system

**To connect TradingView to Predator, we need:**
1. TradingView webhook alerts → HTTP endpoint → Predator
2. Or: TradingView MCP server (separate install) → Elfie tools → Predator

## Status

- DexView market mode: BUILT (static data)
- TradingView desktop app: INSTALLED (not connected)
- TradingView MCP: NOT INSTALLED
- TradingView webhooks: NOT CONFIGURED

## Next Steps

1. Build Predator's own chart display (using lightweight-charts or market_monitor.py data)
2. Optionally: Set up TradingView webhooks for trendline alerts
3. Optionally: Install TradingView MCP server for live data feed
