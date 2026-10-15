"""
Predator Market Scanner — Real CoinGecko data with caching.
"""
import json
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

WATCHLIST_PATH = Path(__file__).parent / "data" / "watchlist.json"
SCANS_PATH = Path(__file__).parent / "data" / "scans"
CACHE_PATH = Path(__file__).parent / "data" / "cache"

CG_BASE = "https://api.coingecko.com/api/v3"

CG_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "DOGE": "dogecoin", "ADA": "cardano", "AVAX": "avalanche-2",
    "LINK": "chainlink", "MATIC": "matic-network",
    # DexView offers these in its dropdown but they were missing here, so the
    # ticker 404'd and the page silently fell back to the last cached price —
    # which is why every asset appeared to show Bitcoin.
    "ZEC": "zcash", "SUI": "sui", "NEAR": "near", "TAO": "bittensor",
    "HYPE": "hyperliquid", "AIP": "aip",
    # BCH/XMR were added to the Bitunix and Kraken maps but missed CG_MAP, which
    # is the dict the ticker and ohlcv routes validate against — so both 404'd.
    "BCH": "bitcoin-cash", "XMR": "monero",
}

# Bitunix futures — the exchange BTC-01 trades on. Used as the primary price
# source because CoinGecko's free tier returns HTTP 429 from this IP, which made
# every scan report price 0.0 and silently poisoned structure detection.
BITUNIX_BASE = "https://fapi.bitunix.com/api/v1/futures/market"

_BITUNIX_MAP = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
    "BNB": "BNBUSDT", "XRP": "XRPUSDT", "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT", "AVAX": "AVAXUSDT", "LINK": "LINKUSDT",
    "MATIC": "MATICUSDT",
    # Verified listed on Bitunix (checked against the live /tickers payload).
    "ZEC": "ZECUSDT", "SUI": "SUIUSDT", "NEAR": "NEARUSDT",
    "TAO": "TAOUSDT", "HYPE": "HYPEUSDT",
    "BCH": "BCHUSDT", "XMR": "XMRUSDT",
    # MATICUSDT still exists on Bitunix but carries ZERO volume — the live market
    # migrated to POLUSDT (Polygon rebrand). Price from MATICUSDT disagreed with
    # Kraken's POL candles by ~3.6x, so point MATIC at POL.
    "MATIC": "POLUSDT", "POL": "POLUSDT",
    # AIP has no Bitunix pair and no CoinGecko listing; it resolves through Kraken.
}

_bt_cache = {"ts": 0, "data": {}}
_BT_TTL = 5  # seconds


def normalize_symbol(symbol):
    """Accept BTC / btc / BTCUSDT / BTC/USDT and return the bare base symbol.

    The standalone server calls this on every market endpoint but it was never
    defined here, so every one of those routes returned HTTP 500.
    """
    if not symbol:
        return ""
    s = str(symbol).strip().upper().replace("/", "").replace("-", "").replace("_", "")
    for base in _BITUNIX_MAP:
        if s == base or s.startswith(base):
            return base
    return s


def fetch_bitunix_prices(symbols=None):
    """Fetch real prices from Bitunix. Returns {SYM: {price, change_24h}}."""
    now = time.time()
    syms = [normalize_symbol(s) for s in symbols] if symbols else list(_BITUNIX_MAP)

    # Cache the FULL board. Bitunix ignores the `symbol` query param and always
    # returns every ticker, so one request serves all symbols.
    if now - _bt_cache["ts"] < _BT_TTL and _bt_cache["data"]:
        return {s: _bt_cache["data"][s] for s in syms if s in _bt_cache["data"]}

    if not [s for s in syms if s in _BITUNIX_MAP]:
        return {}
    try:
        r = requests.get(f"{BITUNIX_BASE}/tickers", timeout=15)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data") or []
        by_pair = {row.get("symbol"): row for row in rows if isinstance(row, dict)}
        out = {}
        for base, pair in _BITUNIX_MAP.items():
            row = by_pair.get(pair)
            if not row:
                continue
            last = float(row.get("lastPrice") or 0)
            opn = float(row.get("open") or 0)
            if last <= 0:
                continue
            # A pair with no traded volume is a dead listing — its lastPrice is
            # stale and will disagree with the candle source. Skip it so the
            # caller falls through to a live pair.
            if float(row.get("baseVol") or 0) <= 0:
                continue
            change = ((last - opn) / opn * 100.0) if opn > 0 else 0.0
            out[base] = {"price": last, "change_24h": change, "source": "bitunix", "pair": pair}
        _bt_cache["ts"] = now
        _bt_cache["data"] = out
        return out
    except Exception as exc:
        print(f"[scanner] bitunix fetch failed: {exc}", flush=True)
        return _bt_cache["data"] if _bt_cache["data"] else {}

# ---------------------------------------------------------------- DEX-only assets
# Assets with no CEX listing. AIPF trades only on Uniswap/Polygon, so neither
# Bitunix nor Kraken carries it. DexScreener's public API is keyless.
DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"

DEX_TOKENS = {
    # base symbol -> contract address on its native chain
    "AIPF": "0x2c72D25530191EBD244Eb6325E1892480b0e6E28",
}


def fetch_dex_price(symbol):
    """Live USD price for a DEX-only token via DexScreener."""
    sym = normalize_symbol(symbol)
    addr = DEX_TOKENS.get(sym)
    url = DEXSCREENER_SEARCH + ("?q=" + addr if addr else "?q=" + sym)
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        if not pairs:
            return None
        # Highest-liquidity pair is the real market.
        pairs.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
        p = pairs[0]
        price = float(p.get("priceUsd") or 0)
        if price <= 0:
            return None
        base = (p.get("baseToken") or {}).get("symbol") or sym
        return {"price": price, "change_24h": 0.0, "source": "dexscreener",
                "pair": p.get("pairAddress"), "base": base}
    except Exception as exc:
        print(f"[scanner] dexscreener {sym} failed: {exc}", file=sys.stderr)
        return None


def fetch_prices(symbols):
    """Fetch prices. Bitunix first (real futures, no key, no rate limit), CoinGecko second.

    CoinGecko's free tier answers HTTP 429 from this IP. The old code treated
    that as "use cache" and, with an empty cache, returned {} — so scan()
    silently reported price 0.0 for every symbol and structure detection ran on
    an empty candle series. Bitunix returns real prices with no key.
    """
    symbols = [normalize_symbol(s) for s in symbols]
    result = fetch_bitunix_prices(symbols)
    if result:
        for sym, info in result.items():
            cache_price(sym, info)
        return result

    # DEX-only assets (e.g. AIPF on Uniswap) have no CEX listing at all.
    dex_out = {}
    remaining = []
    for sym in symbols:
        if sym in DEX_TOKENS:
            d = fetch_dex_price(sym)
            if d:
                dex_out[sym] = d
                cache_price(sym, d)
                continue
        remaining.append(sym)
    if dex_out and not remaining:
        return dex_out
    symbols = remaining

    # Fallback to CoinGecko only if Bitunix is unreachable.
    ids = [CG_MAP[s] for s in symbols if s in CG_MAP]
    if not ids:
        return {}
    
    try:
        url = f"{CG_BASE}/simple/price"
        params = {
            "ids": ",".join(ids),
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        r = requests.get(url, params=params, timeout=10)
        
        if r.status_code == 429:
            # Rate limited — use cache
            return get_cached_prices(symbols)
        
        r.raise_for_status()
        data = r.json()
        if not data and dex_out:
            return dex_out
        
        result = dict(dex_out)
        inv = {v: k for k, v in CG_MAP.items()}
        for cg_id, vals in data.items():
            sym = inv.get(cg_id)
            if sym:
                result[sym] = {
                    "price": float(vals.get("usd", 0)),
                    "change_24h": float(vals.get("usd_24h_change", 0))
                }
                # Cache individual price
                cache_price(sym, result[sym])
        
        return result
    except Exception as e:
        print(f"[scanner] fetch failed: {e}", file=sys.stderr)
        return get_cached_prices(symbols)


def cache_price(symbol, data):
    """Cache price data"""
    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_PATH / f"price_{symbol}.json"
    try:
        cache_file.write_text(json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def get_cached_prices(symbols):
    """Get cached prices for symbols"""
    result = {}
    for sym in symbols:
        cache_file = CACHE_PATH / f"price_{sym}.json"
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                age = (datetime.utcnow() - datetime.fromisoformat(cached["timestamp"])).total_seconds()
                if age < 300:  # 5 min cache
                    result[sym] = cached["data"]
            except Exception:
                pass
    return result


def fetch_ohlcv(cg_id, days="7"):
    """Fetch OHLCV candles.

    Kraken first. This used to call CoinGecko only, which answers HTTP 429 from
    this IP — so it returned [] and every scan reported structure=consolidating
    with empty support/resistance for every symbol. Kraken is keyless and is
    already the primary source everywhere else.
    """
    # Resolve the CoinGecko id back to our symbol so Kraken can serve it.
    inv = {v: k for k, v in CG_MAP.items()}
    sym = inv.get(cg_id)
    if sym:
        try:
            rows = _kraken_ohlcv(sym, 1440 if str(days) in ("90", "1") else 240)
            if len(rows) >= 10:
                # `days` is a WINDOW IN DAYS, not a candle count. It used to be
                # used as `rows[-int(days):]`, so days="7" returned SEVEN 4h
                # candles (28 hours) out of 721. detect_structure() needs a real
                # sample: with 7 closes it read "consolidating" for every symbol
                # and no trader could ever qualify an entry.
                try:
                    want_days = float(days) if str(days).replace(".", "").isdigit() else 7.0
                except ValueError:
                    want_days = 7.0
                if want_days <= 0:
                    want_days = 7.0
                bars_per_day = 1.0 if str(days) in ("90", "1") else 6.0  # 4h candles
                want = int(round(want_days * bars_per_day))
                want = max(20, min(want, len(rows)))   # never fewer than 20 bars
                return rows[-want:]
        except Exception:
            pass

    cache_key = f"ohlcv_{cg_id}_{days}"
    cache_file = CACHE_PATH / f"{cache_key}.json"
    
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            age = (datetime.utcnow() - datetime.fromisoformat(cached["timestamp"])).total_seconds()
            if age < 300:  # 5 min cache
                return cached["data"]
        except Exception:
            pass
    
    try:
        url = f"{CG_BASE}/coins/{cg_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        r = requests.get(url, params=params, timeout=10)
        
        if r.status_code == 429:
            return []
        
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        
        # Convert to candle format (daily)
        candles = []
        for i in range(0, len(prices), 24):
            p = prices[i]
            candles.append({
                "time": int(p[0] / 1000),
                "close": float(p[1])
            })
        
        # Cache
        CACHE_PATH.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "data": candles
        }, ensure_ascii=False), encoding="utf-8")
        
        return candles
    except Exception as e:
        print(f"[scanner] OHLCV fetch failed: {e}", file=sys.stderr)
        return []


def detect_structure(closes):
    """Detect market structure from closes"""
    if len(closes) < 3:
        return "consolidating", 0.5
    
    recent = closes[-7:]
    
    # Count ups and downs
    ups = sum(1 for i in range(len(recent)-1) if recent[i+1] > recent[i])
    downs = sum(1 for i in range(len(recent)-1) if recent[i+1] < recent[i])
    
    if ups > downs * 1.5:
        return "bullish", min(1.0, ups / len(recent))
    elif downs > ups * 1.5:
        return "bearish", min(1.0, downs / len(recent))
    
    return "consolidating", 0.5


def find_sr(closes):
    """Find support and resistance"""
    if len(closes) < 3:
        return {"support": [], "resistance": []}
    
    recent = closes[-14:]  # last 2 weeks
    
    support = []
    resistance = []
    
    for i in range(1, len(recent) - 1):
        if recent[i] < recent[i-1] and recent[i] < recent[i+1]:
            support.append(recent[i])
        if recent[i] > recent[i-1] and recent[i] > recent[i+1]:
            resistance.append(recent[i])
    
    if not support:
        support = [min(recent)]
    if not resistance:
        resistance = [max(recent)]
    
    support = sorted(set(round(s, 2) for s in support if s > 0))[:2]
    resistance = sorted(set(round(r, 2) for r in resistance if r > 0), reverse=True)[:2]
    
    return {"support": support, "resistance": resistance}


def score(symbol, price, change, structure, strength, sr):
    """Score 1-10"""
    score = 5.0
    
    # Structure
    if structure == "bullish":
        score += 1
    elif structure == "bearish":
        score -= 1
    
    # Strength
    score += strength * 2
    
    # Momentum
    if change > 5:
        score += 2
    elif change > 2:
        score += 1
    elif change < -5:
        score -= 2
    elif change < -2:
        score -= 1
    
    # S/R proximity
    if sr["support"] and price > 0:
        dist_to_support = abs(price - sr["support"][0]) / price
        if dist_to_support < 0.02:
            score += 1
    if sr["resistance"] and price > 0:
        dist_to_resistance = abs(price - sr["resistance"][0]) / price
        if dist_to_resistance < 0.01:
            score -= 1
    
    return max(1, min(10, round(score)))


# ─────────────────────────────────────────────────────────────────────────────
# Server-facing API.
#
# standalone-server.py was written against a NEWER scanner than the one the
# Windows export shipped. These seven names were called on every market route
# and did not exist, so those routes degraded instead of failing loudly:
# /api/market/chart returned a null chart, /api/market/setup and /levels fell
# through to 404. Each shim delegates to the real implementation above.
# ─────────────────────────────────────────────────────────────────────────────

LEVELS_PATH = Path(__file__).parent.parent / "support-resistance" / "data" / "levels.json"


def fetch_batch_prices(symbols):
    """{SYM: {'price': float, 'change_24h': float}} — server shape."""
    out = {}
    for sym, info in (fetch_prices([normalize_symbol(s) for s in symbols]) or {}).items():
        out[sym] = {"price": info.get("price", 0), "change_24h": info.get("change_24h", 0)}
    return out


def load_levels(symbol):
    """{'support': [...], 'resistance': [...]} from support-resistance/data/levels.json."""
    sym = normalize_symbol(symbol)
    try:
        data = json.loads(LEVELS_PATH.read_text())
    except Exception:
        return {"support": [], "resistance": []}
    entry = (data.get("symbols") or {}).get(sym) or {}
    return {"support": entry.get("support") or [], "resistance": entry.get("resistance") or []}


def save_levels(symbol, support, resistance):
    try:
        data = json.loads(LEVELS_PATH.read_text())
    except Exception:
        data = {"symbols": {}}
    data.setdefault("symbols", {})[normalize_symbol(symbol)] = {
        "support": support, "resistance": resistance}
    LEVELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEVELS_PATH.write_text(json.dumps(data, indent=2))
    return True


def detect_support_resistance(closes):
    """Server-facing alias for find_sr()."""
    return find_sr(list(closes or []))


def score_setup(symbol, price, change, support, resistance):
    """Server-facing wrapper: derive structure/strength, then score()."""
    closes = []
    cg_id = CG_MAP.get(normalize_symbol(symbol))
    if cg_id:
        try:
            closes = [c["close"] for c in fetch_ohlcv(cg_id, "7")]
        except Exception:
            closes = []
    if not closes:
        px = float(price or 0)
        closes = [px * (1 - 0.01 * k) for k in range(5, 0, -1)] + [px]
    structure, strength = detect_structure(closes)
    sr = {"support": support or [], "resistance": resistance or []}
    return score(normalize_symbol(symbol), float(price or 0),
                 float(change or 0), structure, strength, sr)


def get_latest_scan_prices():
    """{SYM: last_price} from the most recent scan file."""
    try:
        scans = sorted(SCANS_PATH.glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return {}
    for path in scans:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        setups = data.get("setups", data) if isinstance(data, dict) else data
        if isinstance(setups, list):
            out = {s.get("symbol"): s.get("price") for s in setups
                   if isinstance(s, dict) and s.get("price")}
            if out:
                return out
    return {}


async def scan_with_chart(symbol):
    """Chart payload. Real OHLCV + real levels.

    There is no chart-screenshot service wired on this machine (the TradingView
    bridge targets a Windows dev build that does not exist here), so this
    returns the series the UI needs to DRAW its own candles instead of a PNG.
    """
    import asyncio
    sym = normalize_symbol(symbol)
    info = (fetch_prices([sym]) or {}).get(sym, {})
    price = float(info.get("price") or 0)
    change = float(info.get("change_24h") or 0)

    # Kraken first: keyless, returns full OHLCV, and is not rate-limited from
    # this IP. CoinGecko's free tier 429s here and yields a single stub candle,
    # which renders as an empty chart.
    candles, source = [], None
    try:
        rows = _kraken_ohlcv(sym)
        if len(rows) >= 20:
            candles, source = rows[-300:], "kraken"
    except Exception:
        pass
    if not candles:
        try:
            cg_id = CG_MAP.get(sym)
            rows = fetch_ohlcv(cg_id, "7") if cg_id else []
            if len(rows) >= 20:
                candles, source = rows, "coingecko"
        except Exception:
            pass

    closes = [c["close"] for c in candles]
    sr = find_sr(closes) if closes else {"support": [], "resistance": []}
    if not (sr["support"] or sr["resistance"]) and closes:
        sr = detect_support_resistance(closes)
    structure, strength = detect_structure(closes) if closes else ("unknown", 0.0)

    return {
        "symbol": sym,
        "price": price,
        "change_24h": round(change, 2),
        "candles": candles,
        "ohlcv_source": source,
        "support": sr["support"],
        "resistance": sr["resistance"],
        "structure": structure,
        "strength": strength,
        "score": score_setup(sym, price, change, sr["support"], sr["resistance"]) if price else 0,
        "error": None if candles else "no OHLCV available for %s" % sym,
    }


# Kraken OHLC granularity in minutes. The valid set is fixed by the exchange:
# 1, 5, 15, 60, 240, 1440. Anything else must snap to the nearest legal value.
_KRAKEN_INTERVALS = (1, 5, 15, 60, 240, 1440)

_INTERVAL_ALIASES = {
    "1m": 1, "5m": 5, "15m": 15,
    "30m": 30, "1h": 60, "60m": 60, "hourly": 60, "1H": 60,
    "4h": 240, "240m": 240, "4H": 240,
    "1d": 1440, "1440m": 1440, "daily": 1440, "1D": 1440,
}


def kraken_interval_minutes(interval):
    """Map a DexView timeframe label to a legal Kraken interval in minutes."""
    if interval is None:
        return 60
    if isinstance(interval, int):
        want = interval
    else:
        key = str(interval).strip()
        if key.isdigit():
            want = int(key)
        else:
            want = _INTERVAL_ALIASES.get(key, 60)
    return min(_KRAKEN_INTERVALS, key=lambda v: abs(v - want))


def _kraken_ohlcv(symbol, interval=60):
    """Kraken public OHLCV — keyless, used when CoinGecko rate-limits us.

    `interval` is in minutes and must be one of Kraken's legal granularities.
    It was previously hardcoded to 60, which made 1M/5M/15M silently return
    hourly candles labelled as if they were the requested timeframe.
    """
    # Kraken's X/Z-prefix conventions for USD pairs, plus the plain names.
    pairs = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD",
             "XRP": "XRPUSD", "DOGE": "XDGUSD", "ADA": "ADAUSD",
             "ZEC": "ZECUSD", "SUI": "SUIUSD", "NEAR": "NEARUSD",
             # Verified against Kraken's live AssetPairs list: TAO trades as
             # TAO/USD, and MATIC was renamed to POL — Kraken has no MATIC pair,
             # so requesting one silently returned nothing.
             "TAO": "TAOUSD", "HYPE": "HYPEUSD", "LINK": "LINKUSD",
             "AVAX": "AVAXUSD", "MATIC": "POLUSD", "POL": "POLUSD",
             "BNB": "BNBUSD", "BCH": "BCHUSD", "XMR": "XMRUSD"}
    pair = pairs.get(normalize_symbol(symbol))
    if not pair:
        return []
    mins = kraken_interval_minutes(interval)
    r = requests.get("https://api.kraken.com/0/public/OHLC",
                     params={"pair": pair, "interval": mins}, timeout=15)
    r.raise_for_status()
    res = (r.json().get("result") or {})
    # Kraken normalises pair names in the result key (e.g. XBTUSD, XDGUSD), so
    # match on any key that looks like a ticker rather than taking the first one.
    key = None
    for k in res:
        if k == "last" or not isinstance(res.get(k), list):
            continue
        kl = str(k).upper().replace("/", "").replace("-", "").replace("_", "")
        pk = str(pair).upper().replace("/", "").replace("-", "").replace("_", "")
        if kl == pk or kl.replace("XBT", "BTC").replace("XDG", "DOGE") == pk.replace("XBT", "BTC").replace("XDG", "DOGE"):
            key = k
            break
    if key is None:
        for k, v in res.items():
            if isinstance(v, list) and v and isinstance(v[0], list):
                key = k
                break
    if not key or not isinstance(res.get(key), list) or len(res[key]) < 5:
        return []
    rows = []
    for row in res[key][:-1]:
        rows.append({"time": row[0], "open": float(row[1]), "high": float(row[2]),
                     "low": float(row[3]), "close": float(row[4]),
                     "volume": float(row[6]) if len(row) > 6 else 0.0})
    return rows


def scan():
    """Full market scan"""
    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    SCANS_PATH.mkdir(parents=True, exist_ok=True)
    
    # Load watchlist
    with open(WATCHLIST_PATH) as f:
        watchlist = json.load(f)
    
    symbols = [c["symbol"] for c in watchlist["cryptos"]]
    
    # Fetch all prices
    prices = fetch_prices(symbols)
    
    results = []
    for crypto in watchlist["cryptos"]:
        symbol = crypto["symbol"]
        info = prices.get(symbol, {"price": 0, "change_24h": 0})
        price = float(info.get("price", 0))
        change = float(info.get("change_24h", 0))
        
        # Fetch OHLCV for structure
        cg_id = CG_MAP.get(symbol)
        candles = fetch_ohlcv(cg_id, "7") if cg_id else []
        closes = [c["close"] for c in candles]
        
        # Detect structure
        structure, strength = detect_structure(closes)
        
        # Find S/R
        sr = find_sr(closes)
        
        # Score
        final_score = score(symbol, price, change, structure, strength, sr)
        
        results.append({
            "symbol": symbol,
            "name": crypto["name"],
            "price": round(price, 2) if price >= 1 else round(price, 6),
            "change_24h": round(change, 2),
            "structure": structure,
            "strength": round(strength, 2),
            "support": sr["support"],
            "resistance": sr["resistance"],
            "score": final_score,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    # Sort by score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Determine overall market state
    valid = [r for r in results if r.get("score", 0) > 0]
    if valid:
        avg = sum(r["score"] for r in valid) / len(valid)
        market = "bullish" if avg >= 6 else "bearish" if avg <= 3 else "consolidating"
    else:
        market = "consolidating"
    
    # Return the full ranked table. This used to be results[:3], which scanned and
    # scored every symbol and then discarded all but the top three — so the same
    # three setups surfaced on every scan and the rest of the watchlist was wasted
    # work. `limit` lets a caller ask for fewer without hiding the rest.
    limit = None
    try:
        import os as _os
        _l = (_os.environ.get("SCAN_LIMIT") or "").strip()
        if _l.isdigit():
            limit = max(1, int(_l))
    except Exception:
        limit = None

    ranked = results[:limit] if limit else results
    # Explicit rank so the dashboard can order on it.
    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    scan_result = {
        "setups": ranked,
        "market": market,
        "scan_time": datetime.utcnow().isoformat(),
        "count": len(results),
        "returned": len(ranked),
    }
    
    # Save scan
    scan_file = SCANS_PATH / f"scan-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    with open(scan_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    return scan_result


if __name__ == "__main__":
    result = scan()
    print(json.dumps(result, indent=2))
