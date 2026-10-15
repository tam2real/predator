"""
analyst_agent.py -- Analyst Agent
Crypto: Kraken (primary, real trade price) -> CoinGecko (fallback).
Stocks/Indices/Forex/Commodities: yfinance (Yahoo Finance).
No API keys required.
"""

import os
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import shared_state

AGENT_NAME = "analyst"

_CG_KEY = os.getenv("COINGECKO_DEMO_KEY", "")

# --- Ticker maps ---

_KRAKEN_MAP = {
    "BTC":   "XBTUSD",
    "ETH":   "ETHUSD",
    "SOL":   "SOLUSD",
    "DOGE":  "DOGEUSD",
    "LTC":   "LTCUSD",
    "AVAX":  "AVAXUSD",
    "LINK":  "LINKUSD",
    "MATIC": "MATICUSD",
    "BCH":   "BCHUSD",
    "ADA":   "ADAUSD",
    "DOT":   "DOTUSD",
    "XRP":   "XRPUSD",
    "UNI":   "UNIUSD",
    "ATOM":  "ATOMUSD",
    "ARB":   "ARBUSD",
    "OP":    "OPUSD",
    "SUI":   "SUIUSD",
    "APT":   "APTUSD",
    "INJ":   "INJUSD",
    "SHIB":  "SHIBUSD",
}

_CG_MAP = {
    "BTC":   "bitcoin",
    "ETH":   "ethereum",
    "SOL":   "solana",
    "DOGE":  "dogecoin",
    "LTC":   "litecoin",
    "AVAX":  "avalanche-2",
    "LINK":  "chainlink",
    "MATIC": "matic-network",
    "SHIB":  "shiba-inu",
    "BCH":   "bitcoin-cash",
    "ADA":   "cardano",
    "DOT":   "polkadot",
    "XRP":   "ripple",
    "UNI":   "uniswap",
    "ATOM":  "cosmos",
    "ARB":   "arbitrum",
    "OP":    "optimism",
    "SUI":   "sui",
    "APT":   "aptos",
    "INJ":   "injective-protocol",
}

_CRYPTO_SYMBOLS = set(_KRAKEN_MAP.keys()) | set(_CG_MAP.keys())

# Symbols that always route to yfinance
_STOCK_HINTS = {
    "SPY", "QQQ", "DIA", "IWM",        # ETFs / indices
    "SPX", "NDX", "DJI",               # index tickers (mapped below)
    "GLD", "SLV", "GC=F", "SI=F",     # gold / silver futures
    "CL=F", "BZ=F",                    # crude oil
    "EURUSD=X", "GBPUSD=X", "JPYUSD=X",
}

_YF_ALIAS = {
    "SP500": "^GSPC",
    "SPX":   "^GSPC",
    "NDX":   "^NDX",
    "DJI":   "^DJI",
    "NASDAQ": "^IXIC",
    "DOW":   "^DJI",
    "GOLD":  "GC=F",
    "OIL":   "CL=F",
    "SILVER": "SI=F",
}


def _is_crypto(symbol: str) -> bool:
    return symbol.upper() in _CRYPTO_SYMBOLS


def _yf_ticker(symbol: str) -> str:
    s = symbol.upper()
    return _YF_ALIAS.get(s, s)


# --- Kraken fetch ---

def _kraken_price(symbol: str) -> dict:
    """Returns {price, change_24h, volume} or raises."""
    pair = _KRAKEN_MAP.get(symbol.upper())
    if not pair:
        raise ValueError("No Kraken pair for " + symbol)
    url = "https://api.kraken.com/0/public/Ticker"
    r = requests.get(url, params={"pair": pair}, timeout=8)
    if not r.ok:
        raise ValueError("Kraken HTTP " + str(r.status_code))
    body = r.json()
    if body.get("error"):
        raise ValueError("Kraken error: " + str(body["error"]))
    result = body.get("result", {})
    if not result:
        raise ValueError("Kraken: no result for " + pair)
    ticker = next(iter(result.values()))
    price  = float(ticker["c"][0])   # last trade price
    open24 = float(ticker["o"])      # 24h opening price
    volume = float(ticker["v"][1])   # 24h volume
    change = ((price - open24) / open24 * 100) if open24 else 0
    return {"price": price, "change_24h": change, "volume": volume}


# --- CoinGecko fallback ---

def _cg_price(symbol: str) -> dict:
    """Returns {price, change_24h, market_cap} or raises."""
    coin_id = _CG_MAP.get(symbol.upper(), symbol.lower())
    headers = {"x-cg-demo-api-key": _CG_KEY} if _CG_KEY else {}
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }
    for attempt in range(3):
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params=params, headers=headers, timeout=10)
        if r.status_code == 429 and attempt < 2:
            time.sleep(3)
            continue
        break
    if r.status_code == 429:
        raise ValueError("CoinGecko rate limited — add COINGECKO_DEMO_KEY to .env")
    if r.status_code == 426:
        raise ValueError("CoinGecko requires a free demo API key — sign up at coingecko.com and add COINGECKO_DEMO_KEY to .env")
    if not r.ok:
        raise ValueError("CoinGecko HTTP " + str(r.status_code))
    data = r.json().get(coin_id, {})
    if not data:
        raise ValueError("CoinGecko: no data for " + coin_id)
    return {
        "price":      data.get("usd", 0),
        "change_24h": data.get("usd_24h_change", 0),
        "market_cap": data.get("usd_market_cap", 0),
    }


# --- yfinance fetch ---

def _yf_price(symbol: str) -> dict:
    """Returns {price, change_24h, name} or raises."""
    import yfinance as yf
    ticker = _yf_ticker(symbol)
    t = yf.Ticker(ticker)
    info = t.fast_info
    price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
    prev  = getattr(info, "previous_close", None) or getattr(info, "regularMarketPreviousClose", None)
    if price is None:
        raise ValueError("yfinance: no price for " + ticker)
    change = ((price - prev) / prev * 100) if prev else 0
    name = t.info.get("shortName", ticker) if hasattr(t, "info") else ticker
    return {"price": price, "change_24h": change, "name": name}


# --- Public API ---

def get_market_data(symbol: str = "BTC") -> dict:
    s = symbol.strip().upper()
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching " + s)

    try:
        if _is_crypto(s):
            source = "Kraken"
            try:
                d = _kraken_price(s)
                mkt_cap = 0
            except Exception as kraken_err:
                source = "CoinGecko"
                d = _cg_price(s)
                mkt_cap = d.get("market_cap", 0)

            price  = d["price"]
            change = d["change_24h"]
            label  = s

        else:
            source = "Yahoo Finance"
            d = _yf_price(s)
            price  = d["price"]
            change = d["change_24h"]
            label  = d.get("name", s)
            mkt_cap = 0

        direction = "up" if change >= 0 else "down"
        price_fmt = "{:,.2f}".format(price) if price < 1000 else "{:,.0f}".format(price)
        chg_fmt   = "{:.2f}".format(abs(change))
        cap_part  = ""
        if mkt_cap > 1_000_000_000:
            cap_part = " Market cap {:.1f}B.".format(mkt_cap / 1_000_000_000)
        elif mkt_cap > 1_000_000:
            cap_part = " Market cap {:.0f}M.".format(mkt_cap / 1_000_000)

        msg = (
            label + " is at $" + price_fmt + ", "
            + direction + " " + chg_fmt + "% in the last 24 hours."
            + cap_part
            + " (via " + source + ")"
        )

        shared_state.update_agent(AGENT_NAME, status="done", current_task=None,
                                  last_success=s + " @ $" + price_fmt)
        return {
            "success":    True,
            "symbol":     s,
            "price":      price,
            "change_24h": change,
            "market_cap": mkt_cap,
            "source":     source,
            "message":    msg,
        }

    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {
            "success": False,
            "symbol":  s,
            "error":   err,
            "message": "Analyst could not fetch " + s + ": " + err,
        }


def review_setup(symbol: str = "BTC") -> dict:
    data = get_market_data(symbol)
    if not data.get("success"):
        return data
    price = data["price"]
    chg   = data["change_24h"]
    bias  = "bullish" if chg >= 0 else "bearish"
    price_fmt = "{:,.2f}".format(price) if price < 1000 else "{:,.0f}".format(price)
    msg = (
        "Quick setup on " + symbol.upper() + ": price is $"
        + price_fmt + ", "
        + bias + " on the day with a "
        + "{:.2f}".format(abs(chg)) + "% move. "
        + "Where's your entry, stop, and target?"
    )
    return {"success": True, "symbol": symbol, "price": price, "message": msg}


def get_status() -> dict:
    return shared_state.get_agent(AGENT_NAME)
