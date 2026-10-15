"""
bitunix_agent.py -- Bitunix Futures Agent
Crypto futures with leverage. Supports long/short, stop loss, take profit.
API keys: BITUNIX_API_KEY + BITUNIX_SECRET_KEY in root .env
Signature: double SHA256 — SHA256(SHA256(nonce+timestamp+apiKey+sortedParams+body)+secretKey)
"""

import os
import sys
import hashlib
import time
import json
import random
import string
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import shared_state

AGENT_NAME = "bitunix"
_BASE      = "https://fapi.bitunix.com"

def _key():    return os.getenv("BITUNIX_API_KEY", "")
def _secret(): return os.getenv("BITUNIX_SECRET_KEY", "")
def _has_creds(): return bool(_key() and _secret())

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _nonce() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))

def _sign(nonce: str, timestamp: str, query_params: dict = None, body: str = "") -> str:
    """
    digest = SHA256(nonce + timestamp + apiKey + sortedQueryParams + body)
    sign   = SHA256(digest + secretKey)
    sortedQueryParams: keys sorted ascending, concatenated as key1val1key2val2 (no & or =)
    """
    qp = query_params or {}
    sorted_qp = "".join(k + str(qp[k]) for k in sorted(qp.keys()))
    digest = _sha256(nonce + timestamp + _key() + sorted_qp + body)
    return _sha256(digest + _secret())

def _headers(nonce: str, timestamp: str, query_params: dict = None, body: str = "") -> dict:
    return {
        "api-key":      _key(),
        "nonce":        nonce,
        "timestamp":    timestamp,
        "sign":         _sign(nonce, timestamp, query_params, body),
        "Content-Type": "application/json",
    }

def _get(path: str, params: dict = None) -> dict:
    params = params or {}
    n, ts  = _nonce(), str(int(time.time() * 1000))
    qs     = "&".join(k + "=" + str(params[k]) for k in sorted(params.keys()))
    url    = _BASE + path + ("?" + qs if qs else "")
    r      = requests.get(url, headers=_headers(n, ts, params), timeout=10)
    r.raise_for_status()
    data   = r.json()
    if data.get("code") not in (0, None):
        raise ValueError("Bitunix " + data.get("msg", str(data.get("code"))))
    return data.get("data", data)

def _post(path: str, body: dict) -> dict:
    n, ts    = _nonce(), str(int(time.time() * 1000))
    body_str = json.dumps(body, separators=(",", ":"))
    r        = requests.post(_BASE + path,
                             headers=_headers(n, ts, body=body_str),
                             data=body_str, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (0, None):
        raise ValueError("Bitunix " + data.get("msg", str(data.get("code"))))
    return data.get("data", data)

def _guard():
    if not _has_creds():
        return {
            "success": False,
            "account": "bitunix",
            "message": "Bitunix is not connected, Captain. Add BITUNIX_API_KEY and BITUNIX_SECRET_KEY to .env and restart.",
        }
    return None

def _normalize(symbol: str) -> str:
    s = symbol.strip().upper()
    for suffix in ("/USDT", "/USD", "-USDT", "-USD"):
        s = s.replace(suffix, "")
    return s + "USDT"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_account() -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching account")
    try:
        data    = _get("/api/v1/futures/account", {"marginCoin": "USDT"})
        avail   = float(data.get("available", 0))
        frozen  = float(data.get("frozen", 0))
        margin  = float(data.get("margin", 0))
        total   = avail + frozen + margin
        msg = (
            "Bitunix account: available ${:.2f} USDT, "
            "in margin ${:.2f}, frozen ${:.2f}, total ~${:.2f}."
        ).format(avail, margin, frozen, total)
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "account": "bitunix",
                "available": avail, "margin": margin, "total": total, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "account": "bitunix", "error": err,
                "message": "Could not fetch Bitunix account: " + err}


def get_positions() -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching positions")
    try:
        data = _get("/api/v1/futures/position/get_pending_positions")
        positions = data if isinstance(data, list) else []
        if not positions:
            shared_state.update_agent(AGENT_NAME, status="done")
            return {"success": True, "account": "bitunix", "positions": [],
                    "message": "No open Bitunix positions right now."}
        lines = []
        for p in positions:
            sym  = p.get("symbol", "?")
            side = p.get("side", "?")
            qty  = p.get("available", p.get("qty", "?"))
            pnl  = float(p.get("unrealisedPnl", p.get("pnl", 0)))
            lev  = p.get("leverage", "?")
            lines.append("{} {} {}x qty {} PnL ${:.2f}".format(sym, side, lev, qty, pnl))
        msg = "Bitunix positions: " + " | ".join(lines)
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "account": "bitunix", "positions": positions, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "account": "bitunix", "error": err,
                "message": "Could not fetch Bitunix positions: " + err}


def open_position(symbol: str = "BTC", side: str = "buy",
                  notional_usd: float = 100, leverage: int = 5,
                  stop_pct: float = 1.0, take_profit_pct: float = 3.0) -> dict:
    """
    Open a leveraged futures position.
    side: "buy" = long, "sell" = short
    notional_usd: margin collateral (e.g. 100 = $100 margin)
    """
    g = _guard()
    if g: return g

    sym       = _normalize(symbol)
    direction = "LONG" if side.lower() in ("buy", "long") else "SHORT"
    trade_side = "BUY" if direction == "LONG" else "SELL"

    shared_state.update_agent(AGENT_NAME, status="running",
                              current_task="Open " + direction + " " + sym)
    try:
        # Set leverage
        _post("/api/v1/futures/leverage/set",
              {"symbol": sym, "leverage": str(leverage), "marginCoin": "USDT"})

        # Get current price for qty calc
        ticker_data = _get("/api/v1/futures/market/detail", {"symbol": sym})
        price = float(ticker_data.get("lastPr", ticker_data.get("price", 0)))
        if not price:
            raise ValueError("Could not fetch " + sym + " price")

        position_value = notional_usd * leverage
        qty = round(position_value / price, 6)

        # Place market order
        order_body = {
            "symbol":     sym,
            "marginCoin": "USDT",
            "side":       trade_side,
            "tradeSide":  direction,
            "orderType":  "market",
            "qty":        str(qty),
        }
        result   = _post("/api/v1/futures/order/place", order_body)
        order_id = str(result.get("orderId", result.get("id", "?")))

        # Calculate stop and TP from entry price
        if direction == "LONG":
            stop_price = round(price * (1 - stop_pct / 100), 2)
            tp_price   = round(price * (1 + take_profit_pct / 100), 2)
        else:
            stop_price = round(price * (1 + stop_pct / 100), 2)
            tp_price   = round(price * (1 - take_profit_pct / 100), 2)

        msg = (
            "Bitunix {dir} opened: {sym} {lev}x. "
            "Margin ${col}, position ~${pos:.0f}. "
            "Entry ~${entry:.2f}, stop ${stop:.2f} ({sp}% away), "
            "TP ${tp:.2f} ({tpp}% away). Order: {oid}."
        ).format(
            dir=direction, sym=sym, lev=leverage,
            col=notional_usd, pos=position_value,
            entry=price, stop=stop_price, sp=stop_pct,
            tp=tp_price, tpp=take_profit_pct,
            oid=order_id[:10],
        )

        shared_state.update_agent(AGENT_NAME, status="done",
                                  last_success=direction + " " + sym + " @ " + str(price))
        return {
            "success":           True,
            "account":           "bitunix",
            "symbol":            sym,
            "side":              direction,
            "leverage":          leverage,
            "notional_usd":      notional_usd,
            "position_size_usd": position_value,
            "entry_price":       price,
            "stop_price":        stop_price,
            "take_profit_price": tp_price,
            "order_id":          order_id,
            "message":           msg,
        }

    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "account": "bitunix", "error": err,
                "message": "Bitunix order failed: " + err}


def close_position(symbol: str = "BTC") -> dict:
    g = _guard()
    if g: return g
    sym = _normalize(symbol)
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Closing " + sym)
    try:
        _post("/api/v1/futures/order/close_position",
              {"symbol": sym, "marginCoin": "USDT"})
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "account": "bitunix",
                "message": "Bitunix position in " + sym + " closed."}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "account": "bitunix", "error": err,
                "message": "Could not close " + sym + ": " + err}


def get_status() -> dict:
    state = shared_state.get_agent(AGENT_NAME)
    state["bitunix_connected"] = _has_creds()
    state["mode"]     = "live_futures"
    state["exchange"] = "bitunix"
    return state
