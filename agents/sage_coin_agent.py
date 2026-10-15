"""
sage_coin_agent.py — $SAGE meme coin tracker (Solana / pump.fun)
Uses Dexscreener free API — no key required.
CA: FTnmGjTcvgf4XEBtA4RY1z7jLXaocDQz5amzoSvApump
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path

# Allow sibling imports when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))
import shared_state

AGENT_NAME = "sage_coin"

SAGE_CA        = "FTnmGjTcvgf4XEBtA4RY1z7jLXaocDQz5amzoSvApump"
PUMP_FUN_URL   = "https://pump.fun/coin/" + SAGE_CA
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/" + SAGE_CA

ALERT_THRESHOLD_PCT = float(os.getenv("SAGE_COIN_ALERT_PCT", "20.0"))
TIMEOUT = 8  # seconds


def _fetch_pairs() -> list:
    """Fetch token pairs from Dexscreener. Returns list of pair dicts."""
    r = requests.get(DEXSCREENER_URL, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    pairs = data.get("pairs") or []
    if not pairs:
        raise ValueError("No trading pairs found for $SAGE yet — token may still be on bonding curve.")
    # Sort by liquidity descending so pairs[0] is the main pool
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0, reverse=True)
    return pairs


def _format_price(price_usd: float) -> str:
    """Return a TTS-safe price string."""
    if price_usd >= 0.01:
        return "${:.4f}".format(price_usd)
    elif price_usd >= 0.000001:
        return "${:.8f}".format(price_usd)
    else:
        return "${:.2e}".format(price_usd)


def _fmt_volume(v: float) -> str:
    if v >= 1_000_000:
        return "${:.1f}M".format(v / 1_000_000)
    elif v >= 1_000:
        return "${:.1f}K".format(v / 1_000)
    return "${:.0f}".format(v)


# ── Public agent functions ────────────────────────────────────────────────────

def get_price() -> dict:
    """
    Returns {"success": True, "price_usd": float, "change_24h": float, "message": str}
    """
    shared_state.update_agent(AGENT_NAME, status="running", current_task="get_price")
    try:
        pairs = _fetch_pairs()
        p0    = pairs[0]
        price = float(p0.get("priceUsd") or 0)
        chg   = float((p0.get("priceChange") or {}).get("h24") or 0)
        direction = "up" if chg >= 0 else "down"
        msg = "$SAGE is at {}, {} {:.1f}% in the last 24 hours.".format(
            _format_price(price), direction, abs(chg))
        shared_state.update_agent(AGENT_NAME, status="done",
                                  last_success=datetime.utcnow().isoformat())
        return {"success": True, "price_usd": price, "change_24h": chg, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "message": "Couldn't get $SAGE price right now. " + err,
                "price_usd": None, "change_24h": None}


def get_full_stats() -> dict:
    """
    Returns full stats: price, change_24h, volume_24h, market_cap, liquidity, fdv, message
    """
    shared_state.update_agent(AGENT_NAME, status="running", current_task="get_full_stats")
    try:
        pairs = _fetch_pairs()
        p0    = pairs[0]
        price    = float(p0.get("priceUsd") or 0)
        chg      = float((p0.get("priceChange") or {}).get("h24") or 0)
        vol_24h  = float((p0.get("volume") or {}).get("h24") or 0)
        mcap     = float(p0.get("marketCap") or p0.get("fdv") or 0)
        liq      = float((p0.get("liquidity") or {}).get("usd") or 0)
        fdv      = float(p0.get("fdv") or 0)

        direction = "up" if chg >= 0 else "down"
        parts = [
            "$SAGE is at {}, {} {:.1f}% in 24 hours.".format(
                _format_price(price), direction, abs(chg)),
        ]
        if vol_24h > 0:
            parts.append("Volume: {}.".format(_fmt_volume(vol_24h)))
        if mcap > 0:
            parts.append("Market cap: {}.".format(_fmt_volume(mcap)))
        if liq > 0:
            parts.append("Liquidity: {}.".format(_fmt_volume(liq)))
        parts.append("Chart: pump.fun")

        msg = " ".join(parts)
        shared_state.update_agent(AGENT_NAME, status="done",
                                  last_success=datetime.utcnow().isoformat())
        return {
            "success":    True,
            "message":    msg,
            "price_usd":  price,
            "change_24h": chg,
            "volume_24h": vol_24h,
            "market_cap": mcap,
            "liquidity":  liq,
            "fdv":        fdv,
            "pump_url":   PUMP_FUN_URL,
        }
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "message": "Couldn't get $SAGE stats right now. " + err}


def get_status() -> dict:
    """Standard agent status check."""
    state = shared_state.get_agent(AGENT_NAME)
    return {
        "success":  True,
        "message":  "sage_coin agent is live. CA: " + SAGE_CA,
        "status":   state.get("status", "idle"),
        "last_success": state.get("last_success"),
        "last_error":   state.get("last_error"),
        "pump_url": PUMP_FUN_URL,
    }
