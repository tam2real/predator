# Market Scanner

Scans top 10 cryptos for support/resistance levels. Cron job every 4 hours.

## Watchlist
BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, MATIC

## Process
1. Pull daily OHLC from CoinGecko/TradingView
2. Identify support/resistance levels
3. Score each setup 1-10
4. Rank top 3

## Output
- Top 3 setups with entry, stop, target, confidence
- Market trend (bullish/bearish)

## Cron Schedule
Every 4 hours during market hours

## Status: PLANNED