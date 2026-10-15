"""
market_monitor.py -- Crypto Market Monitor
Tracks BTC, Total Market Cap, Total2, Total3.
Detects significant moves (5%+), support bounces, and trend shifts.
Used by boot greeting (alert only when something notable) and background monitoring.
"""

import os
import time
import threading
import requests

# Alert threshold — % change that triggers a notification
ALERT_THRESHOLD = float(os.getenv("MARKET_ALERT_THRESHOLD", "5.0"))
# Background check interval in seconds (default 20 min)
CHECK_INTERVAL  = int(os.getenv("MARKET_CHECK_INTERVAL", "1200"))

_last_alert_time = {}   # symbol -> timestamp, prevents spam
_ALERT_COOLDOWN  = 3600  # 1 hour between same-symbol alerts

_pending_alerts  = []   # queue for frontend to poll
_alerts_lock     = threading.Lock()

_CG_KEY = os.getenv("COINGECKO_DEMO_KEY", "")
_CG_HEADERS = {"x-cg-demo-api-key": _CG_KEY} if _CG_KEY else {}


# ── Data fetchers ─────────────────────────────────────────────────────────────

def _fetch_btc() -> dict:
    """BTC price + 24h change via Kraken (primary) or CoinGecko (fallback)."""
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker",
                         params={"pair": "XBTUSD"}, timeout=8)
        data   = r.json().get("result", {})
        ticker = next(iter(data.values()), {})
        price  = float(ticker["c"][0])
        open24 = float(ticker["o"])
        change = (price - open24) / open24 * 100 if open24 else 0
        high   = float(ticker["h"][1])
        low    = float(ticker["l"][1])
        return {"price": price, "change_24h": change,
                "high_24h": high, "low_24h": low, "source": "kraken"}
    except Exception:
        pass
    # CoinGecko fallback
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            headers=_CG_HEADERS, timeout=8)
        if r.status_code == 426:
            raise ValueError("CoinGecko requires a demo API key — add COINGECKO_DEMO_KEY to .env")
        r.raise_for_status()
        d = r.json().get("bitcoin", {})
        return {"price": d.get("usd", 0), "change_24h": d.get("usd_24h_change", 0),
                "high_24h": 0, "low_24h": 0, "source": "coingecko"}
    except Exception as e:
        raise ValueError("BTC fetch failed: " + str(e))


def _fetch_global() -> dict:
    """Total market cap, Total2, Total3 via CoinGecko /global."""
    r = requests.get("https://api.coingecko.com/api/v3/global",
                     headers=_CG_HEADERS, timeout=10)
    r.raise_for_status()
    g = r.json().get("data", {})

    total_mcap = g.get("total_market_cap", {}).get("usd", 0)
    change_24h = g.get("market_cap_change_percentage_24h_usd", 0)
    btc_dom    = g.get("market_cap_percentage", {}).get("btc", 0)
    eth_dom    = g.get("market_cap_percentage", {}).get("eth", 0)

    # Total2 = total minus BTC
    btc_mcap = total_mcap * btc_dom / 100
    total2   = total_mcap - btc_mcap

    # Total3 = total minus BTC and ETH (pure altcoin market)
    eth_mcap = total_mcap * eth_dom / 100
    total3   = total_mcap - btc_mcap - eth_mcap

    return {
        "total_mcap":   total_mcap,
        "total2_mcap":  total2,
        "total3_mcap":  total3,
        "change_24h":   change_24h,
        "btc_dominance": btc_dom,
        "eth_dominance": eth_dom,
    }


# ── Signal analysis ───────────────────────────────────────────────────────────

def _mcap_label(val: float) -> str:
    if val >= 1e12:
        return "{:.2f}T".format(val / 1e12)
    if val >= 1e9:
        return "{:.1f}B".format(val / 1e9)
    return "{:.0f}M".format(val / 1e6)


def _direction_word(change: float) -> str:
    if change >= 0:
        return "up"
    return "down"


def _market_signal(btc_change: float, total_change: float,
                   btc_price: float, btc_high: float, btc_low: float) -> str:
    """
    Return a trading signal string. Empty string = nothing notable.
    Signals: big move alert, support bounce, resistance test, trend shift.
    """
    signals = []
    abs_btc   = abs(btc_change)
    abs_total = abs(total_change)

    # Big move alert
    if abs_btc >= 5:
        direction = "surging" if btc_change > 0 else "dropping"
        signals.append(
            "BTC is {} {:.1f}% in the last 24 hours — that's a significant move.".format(
                direction, abs_btc)
        )

    if abs_total >= 5 and abs_btc < 5:
        direction = "up" if total_change > 0 else "down"
        signals.append(
            "Total crypto market is {} {:.1f}% — altcoins are moving.".format(
                direction, abs_total)
        )

    # Support/resistance context
    if btc_high > 0 and btc_low > 0 and btc_price > 0:
        range_size = btc_high - btc_low
        pos_in_range = (btc_price - btc_low) / range_size if range_size > 0 else 0.5

        if btc_change < -2 and pos_in_range < 0.2:
            signals.append(
                "BTC is near its 24-hour low — watch for support around ${:,.0f}.".format(btc_low)
            )
        elif btc_change > 0 and pos_in_range > 0.85:
            signals.append(
                "BTC is testing its 24-hour high at ${:,.0f} — watch for resistance.".format(btc_high)
            )
        elif btc_change < -4 and pos_in_range > 0.3:
            signals.append(
                "BTC dropped {:.1f}% but is holding above the day low — possible support.".format(abs_btc)
            )

    # Buy/sell bias
    if btc_change <= -5:
        signals.append("Could be a buy opportunity if it finds support — watch price action, Captain.")
    elif btc_change >= 5:
        signals.append("Strong momentum — look to take profits or trail your stop.")
    elif -1 <= btc_change <= 1 and abs_total >= 3:
        signals.append("BTC flat but alts moving — Total3 showing altcoin activity.")

    return " ".join(signals)


# ── Public API ────────────────────────────────────────────────────────────────

def get_market_snapshot() -> dict:
    """Full market snapshot: BTC + global caps + signals. Used on demand."""
    try:
        btc    = _fetch_btc()
        globl  = _fetch_global()
        signal = _market_signal(
            btc["change_24h"], globl["change_24h"],
            btc["price"], btc.get("high_24h", 0), btc.get("low_24h", 0)
        )
        return {
            "success": True,
            "btc_price":    btc["price"],
            "btc_change":   btc["change_24h"],
            "total_mcap":   globl["total_mcap"],
            "total2_mcap":  globl["total2_mcap"],
            "total3_mcap":  globl["total3_mcap"],
            "total_change": globl["change_24h"],
            "btc_dom":      globl["btc_dominance"],
            "signal":       signal,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "signal": ""}


def get_boot_alert() -> str:
    """
    Returns a short alert string for the boot greeting — ONLY if something notable.
    Empty string = nothing significant, boot stays quiet.
    """
    try:
        snap = get_market_snapshot()
        if not snap["success"]:
            return ""
        signal = snap["signal"]
        if not signal:
            return ""
        # Build a concise boot line
        btc_price  = snap["btc_price"]
        btc_change = snap["btc_change"]
        direction  = _direction_word(btc_change)
        total_label = _mcap_label(snap["total_mcap"])
        total3_label = _mcap_label(snap["total3_mcap"])

        lines = [
            "Market alert: BTC at ${:,.0f}, {} {:.1f}% today.".format(
                btc_price, direction, abs(btc_change)),
            "Total market cap {}, Total3 {}.".format(total_label, total3_label),
            signal,
        ]
        return " ".join(lines)
    except Exception:
        return ""


def get_market_summary() -> str:
    """Spoken market summary for on-demand queries."""
    try:
        snap = get_market_snapshot()
        if not snap["success"]:
            return "Couldn't fetch market data right now, Captain."

        btc_dir   = _direction_word(snap["btc_change"])
        tot_dir   = _direction_word(snap["total_change"])

        lines = [
            "BTC at ${:,.0f}, {} {:.1f}% in 24 hours.".format(
                snap["btc_price"], btc_dir, abs(snap["btc_change"])),
            "Total market cap {}, {} {:.1f}%.".format(
                _mcap_label(snap["total_mcap"]), tot_dir, abs(snap["total_change"])),
            "Total3 (alts ex BTC and ETH) at {}.".format(
                _mcap_label(snap["total3_mcap"])),
            "BTC dominance {:.1f}%.".format(snap["btc_dom"]),
        ]
        if snap["signal"]:
            lines.append(snap["signal"])

        return " ".join(lines)
    except Exception as e:
        return "Market data unavailable: " + str(e)


# ── Pending alerts queue (frontend polls /market-alerts) ──────────────────────

def push_alert(message: str):
    """Add an alert to the queue for the frontend to pick up."""
    with _alerts_lock:
        _pending_alerts.append({
            "message": message,
            "ts": int(time.time()),
        })
        # Keep only last 10
        if len(_pending_alerts) > 10:
            _pending_alerts.pop(0)


def pop_alerts() -> list:
    """Drain and return all pending alerts."""
    with _alerts_lock:
        alerts = list(_pending_alerts)
        _pending_alerts.clear()
    return alerts


# ── Background monitor thread ─────────────────────────────────────────────────

_monitor_thread = None
_monitor_running = False


def _monitor_loop():
    global _monitor_running
    print("[MARKET] Background monitor started — checking every {}s".format(CHECK_INTERVAL))
    while _monitor_running:
        try:
            snap = get_market_snapshot()
            if snap["success"] and snap["signal"]:
                symbol = "BTC"
                now    = time.time()
                last   = _last_alert_time.get(symbol, 0)
                if now - last > _ALERT_COOLDOWN:
                    _last_alert_time[symbol] = now
                    alert_msg = (
                        "Market update, Captain. "
                        + "BTC at ${:,.0f}, {} {:.1f}% today. ".format(
                            snap["btc_price"],
                            _direction_word(snap["btc_change"]),
                            abs(snap["btc_change"]))
                        + snap["signal"]
                    )
                    push_alert(alert_msg)
                    print("[MARKET] Alert queued: " + alert_msg[:80])
        except Exception as e:
            print("[MARKET] Monitor loop error: " + str(e))

        # Sleep in small chunks so the thread can stop cleanly
        for _ in range(CHECK_INTERVAL):
            if not _monitor_running:
                break
            time.sleep(1)

    print("[MARKET] Background monitor stopped.")


def start_monitor():
    """Start background market monitoring thread. Call once at server start."""
    global _monitor_thread, _monitor_running
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    global _monitor_running
    _monitor_running = False
