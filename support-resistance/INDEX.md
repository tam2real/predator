---
status: active
domain: ultimate-skill
type: index
skill: predator
updated: 2026-10-01
---

# Predator Support-Resistance — Level Detection

This sub-skill detects and tracks key support and resistance levels for trading.

## Structure

| Sub-folder | Purpose |
|------------|---------|
| `data/` | Historical level data, cached computations |

## Files

| File | Purpose |
|------|---------|
| `data/levels.json` | Computed S/R levels with timestamps and strength scores |

## How It Executes

- Entry: called by Predator's market scanner (`market-scanner/`) when scanning symbols
- Dependencies: price data from TradingView API, volume profile data
- Output: updates `data/levels.json`; levels consumed by trade-signals and risk-manager

## Status

Core level detection implemented. Dashboard integration pending (see Predator main INDEX).