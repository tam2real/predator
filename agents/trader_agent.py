"""
trader_agent.py -- Trader Agent
Alpaca paper trading. No real exchange. No real money.
Lazy credential loading -- reads .env at call time, not import time.
"""

import os
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import shared_state

AGENT_NAME = "trader"

# ── Lazy credentials (read at call time, never at import) ─────────────────────
def _key():    return os.getenv("ALPACA_API_KEY", "")
def _secret(): return os.getenv("ALPACA_SECRET_KEY", "")
def _base():   return os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
def _has_creds(): return bool(_key() and _secret())

def _headers():
    return {
        "APCA-API-KEY-ID":     _key(),
        "APCA-API-SECRET-KEY": _secret(),
        "Content-Type":        "application/json",
    }

# ── Crypto symbol normalization ───────────────────────────────────────────────
_CRYPTO = {"BTC","ETH","SOL","DOGE","LTC","AVAX","LINK","MATIC","SHIB","BCH",
           "ADA","DOT","XRP","UNI","ATOM","ARB","OP","SUI","APT"}

def _normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper().replace("-USD","").replace("/USD","")
    if s in _CRYPTO:
        return s + "/USD"
    return s

# ── Guard ─────────────────────────────────────────────────────────────────────
def _guard():
    if not _has_creds():
        return {
            "success": False,
            "message": "Trader is not connected. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env and restart.",
        }
    return None

# ── API helpers ───────────────────────────────────────────────────────────────
def _get(path: str) -> dict:
    r = requests.get(_base() + path, headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

def _post(path: str, body: dict) -> dict:
    r = requests.post(_base() + path, headers=_headers(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()

def _delete(path: str) -> dict:
    r = requests.delete(_base() + path, headers=_headers(), timeout=10)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"status": "ok"}

# ── Commands ──────────────────────────────────────────────────────────────────
def get_account() -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching account")
    try:
        data = _get("/account")
        equity    = float(data.get("equity", 0))
        cash      = float(data.get("cash", 0))
        buying_pw = float(data.get("buying_power", 0))
        pnl       = float(data.get("unrealized_pl", 0))
        msg = (
            "Paper account: equity {:.0f} dollars, cash {:.0f}, buying power {:.0f}. "
            "Unrealized PnL today: {:.2f} dollars."
        ).format(equity, cash, buying_pw, pnl)
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "equity": equity, "cash": cash, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Could not fetch account: " + err}


def get_positions() -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching positions")
    try:
        positions = _get("/positions")
        if not positions:
            shared_state.update_agent(AGENT_NAME, status="done")
            return {"success": True, "positions": [], "message": "No open positions right now."}
        lines = []
        for p in positions:
            sym  = p.get("symbol","?")
            qty  = p.get("qty","?")
            pnl  = float(p.get("unrealized_pl", 0))
            side = p.get("side","?")
            lines.append(sym + " " + str(qty) + " shares " + side + ", PnL " + "{:.2f}".format(pnl))
        msg = "Open positions: " + ". ".join(lines) + "."
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "positions": positions, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Could not fetch positions: " + err}


def place_order(symbol: str = "BTC", qty: str = "1", side: str = "buy",
                order_type: str = "market", limit_price=None, time_in_force: str = "gtc") -> dict:
    g = _guard()
    if g: return g
    sym = _normalize_symbol(symbol)
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Placing " + side + " " + sym)
    try:
        body = {
            "symbol":        sym,
            "qty":           str(qty),
            "side":          side.lower(),
            "type":          order_type.lower(),
            "time_in_force": time_in_force.lower(),
        }
        if order_type.lower() == "limit" and limit_price:
            body["limit_price"] = str(limit_price)
        data = _post("/orders", body)
        order_id = data.get("id","?")[:8]
        msg = (
            "Order placed. Paper " + side + " " + str(qty) + " " + sym
            + " at " + order_type + ". Order ID: " + order_id + "."
        )
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "order_id": data.get("id"), "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Order failed: " + err}


def close_position(symbol: str = "") -> dict:
    g = _guard()
    if g: return g
    sym = _normalize_symbol(symbol)
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Closing " + sym)
    try:
        data = _delete("/positions/" + sym)
        msg = "Closed position in " + sym + "."
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Could not close " + sym + ": " + err}


def close_all_positions() -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Closing all positions")
    try:
        _delete("/positions")
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "message": "All positions closed and orders cancelled."}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Could not close all: " + err}


def get_orders(limit: int = 5) -> dict:
    g = _guard()
    if g: return g
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Fetching orders")
    try:
        orders = _get("/orders?status=all&limit=" + str(limit))
        if not orders:
            shared_state.update_agent(AGENT_NAME, status="done")
            return {"success": True, "orders": [], "message": "No recent orders found."}
        lines = []
        for o in orders[:limit]:
            sym    = o.get("symbol","?")
            side   = o.get("side","?")
            qty    = o.get("qty","?")
            status = o.get("status","?")
            lines.append(sym + " " + side + " " + str(qty) + " - " + status)
        msg = "Last " + str(len(lines)) + " orders: " + ". ".join(lines) + "."
        shared_state.update_agent(AGENT_NAME, status="done")
        return {"success": True, "orders": orders, "message": msg}
    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {"success": False, "error": err, "message": "Could not fetch orders: " + err}


def review_setup(symbol: str = "BTC") -> dict:
    """Pull live price from analyst then ask for trade plan."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from analyst_agent import get_market_data
        price_data = get_market_data(symbol)
        if price_data.get("success"):
            price = price_data["price"]
            msg = (
                "Current price for " + symbol.upper() + " is "
                + "{:.0f}".format(price) + " dollars. "
                + "Give me your entry, stop loss, and target to review the setup."
            )
        else:
            msg = (
                "Paper account is connected and ready. "
                + "What's the setup? Give me entry, stop, and target."
            )
    except Exception:
        msg = (
            "Paper account is connected and ready. "
            + "What's the setup? Give me entry, stop, and target."
        )
    return {"success": True, "message": msg}



def buy_with_stop(symbol: str = "BTC", notional_usd: float = None,
                  qty: float = None, stop_pct: float = 1.0) -> dict:
    """
    Buy crypto at market then immediately place a limit sell as stop loss.
    Crypto on Alpaca only supports market + limit orders (no native stop type).
    The limit sell sits at entry * (1 - stop_pct/100) — fires if price drops.

    Args:
        symbol      : e.g. "BTC", "ETH"
        notional_usd: dollar amount to spend (e.g. 100). Use this OR qty.
        qty         : exact coin qty to buy. Use this OR notional_usd.
        stop_pct    : stop loss % below entry. Default 1.0 (1%).
    """
    import time as _time
    g = _guard()
    if g:
        return g

    sym = _normalize_symbol(symbol)
    shared_state.update_agent(AGENT_NAME, status="running",
                              current_task="Buy+stop " + sym)
    try:
        # ── 1. Get live price from Alpaca data feed ──
        base_sym = sym.replace("/USD", "")
        price_url = (
            "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades"
            "?symbols=" + sym
        )
        pr = requests.get(price_url, headers=_headers(), timeout=8)
        pr.raise_for_status()
        trade_data = pr.json().get("trades", {}).get(sym, {})
        live_price = float(trade_data.get("p", 0))
        if not live_price:
            raise ValueError("Could not fetch live price for " + sym)

        # ── 2. Resolve qty ──
        if notional_usd and not qty:
            buy_qty = round(notional_usd / live_price, 6)
        elif qty:
            buy_qty = float(qty)
        else:
            raise ValueError("Provide notional_usd or qty.")

        # ── 3. Market buy ──
        buy_body = {
            "symbol":        sym,
            "qty":           str(buy_qty),
            "side":          "buy",
            "type":          "market",
            "time_in_force": "gtc",
        }
        rb = _post("/orders", buy_body)
        buy_id = rb.get("id", "?")

        # ── 4. Wait for fill, read actual fill price ──
        fill_price = live_price
        for _ in range(6):
            _time.sleep(1)
            order_info = _get("/orders/" + buy_id)
            if order_info.get("status") == "filled":
                fp = order_info.get("filled_avg_price")
                if fp:
                    fill_price = float(fp)
                break

        # ── 5. Place limit sell as stop loss ──
        stop_price = round(fill_price * (1 - stop_pct / 100), 2)
        filled_qty = float(order_info.get("filled_qty", buy_qty))

        stop_body = {
            "symbol":        sym,
            "qty":           str(filled_qty),
            "side":          "sell",
            "type":          "limit",
            "limit_price":   str(stop_price),
            "time_in_force": "gtc",
        }
        rs = _post("/orders", stop_body)
        stop_id = rs.get("id", "?")

        msg = (
            "Bought {qty} {sym} at ${fill:.2f}. "
            "Stop-loss limit sell placed at ${stop:.2f} ({pct}% below entry). "
            "Buy ID: {bid}. Stop ID: {sid}."
        ).format(
            qty=filled_qty, sym=sym,
            fill=fill_price, stop=stop_price, pct=stop_pct,
            bid=buy_id[:8], sid=stop_id[:8],
        )

        shared_state.update_agent(AGENT_NAME, status="done",
                                  last_success=sym + " buy+stop @ " + str(fill_price))
        return {
            "success":     True,
            "symbol":      sym,
            "qty":         filled_qty,
            "fill_price":  fill_price,
            "stop_price":  stop_price,
            "stop_pct":    stop_pct,
            "buy_order_id": buy_id,
            "stop_order_id": stop_id,
            "message":     msg,
        }

    except Exception as e:
        err = str(e)
        shared_state.update_agent(AGENT_NAME, status="failed", last_error=err)
        return {
            "success": False,
            "symbol":  symbol,
            "error":   err,
            "message": "buy_with_stop failed: " + err,
        }


def get_status() -> dict:
    state = shared_state.get_agent(AGENT_NAME)
    state["alpaca_connected"] = _has_creds()
    state["mode"] = "paper"
    state["exchange"] = "alpaca"
    return state
