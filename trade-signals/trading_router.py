"""
trading_router.py -- Multi-Account Trading Router
Knows all trading accounts. When a trade comes in without a specified account,
returns a prompt asking which account to use. Sage speaks it, user picks one.

Accounts:
  alpaca                -- Alpaca paper trading ($5k paper, buy-only crypto)
  bitunix               -- Bitunix live futures (leverage/shorts, no funds yet)
  coinbase              -- Coinbase (crypto + stocks, API keys needed)
  kraken                -- Kraken (no funds right now)
  breakout_prop_scalp   -- Breakout Prop scalp account (manual)
  breakout_prop_interm  -- Breakout Prop intermediate account (manual)
  breakout_prop_long    -- Breakout Prop long-term account (manual)
"""

import os
from pathlib import Path

ACCOUNTS = {
    "alpaca": {
        "name":        "Alpaca paper trading",
        "type":        "paper",
        "supports":    ["buy", "sell", "stop_loss"],
        "leverage":    False,
        "short":       False,
        "api":         True,
        "env_keys":    ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
        "note":        "Paper money only. Buy-only crypto. No leverage.",
    },
    "bitunix": {
        "name":        "Bitunix",
        "type":        "live_futures",
        "supports":    ["long", "short", "leverage", "stop_loss", "take_profit"],
        "leverage":    True,
        "short":       True,
        "api":         True,
        "env_keys":    ["BITUNIX_API_KEY", "BITUNIX_SECRET_KEY"],
        "note":        "Live crypto futures with leverage. No funds loaded yet.",
    },
    "coinbase": {
        "name":        "Coinbase",
        "type":        "live",
        "supports":    ["buy", "sell", "crypto", "stocks"],
        "leverage":    False,
        "short":       False,
        "api":         True,
        "env_keys":    ["COINBASE_API_KEY", "COINBASE_API_SECRET"],
        "note":        "Live crypto and stocks. API keys needed.",
    },
    "kraken": {
        "name":        "Kraken",
        "type":        "live",
        "supports":    ["buy", "sell", "crypto"],
        "leverage":    False,
        "short":       False,
        "api":         True,
        "env_keys":    ["KRAKEN_API_KEY", "KRAKEN_SECRET_KEY"],
        "note":        "No funds loaded right now.",
    },
    "breakout_prop_scalp": {
        "name":        "Breakout Prop — Scalp",
        "type":        "manual_prop",
        "supports":    ["log_trade", "review_setup"],
        "leverage":    True,
        "short":       True,
        "api":         False,
        "env_keys":    [],
        "note":        "Short-term scalp prop account. Manual — Sage tracks setups.",
        "account_sub": "scalp",
    },
    "breakout_prop_interm": {
        "name":        "Breakout Prop — Intermediate",
        "type":        "manual_prop",
        "supports":    ["log_trade", "review_setup"],
        "leverage":    True,
        "short":       True,
        "api":         False,
        "env_keys":    [],
        "note":        "Swing/intermediate prop account. Manual — Sage tracks setups.",
        "account_sub": "intermediate",
    },
    "breakout_prop_long": {
        "name":        "Breakout Prop — Long Term",
        "type":        "manual_prop",
        "supports":    ["log_trade", "review_setup"],
        "leverage":    True,
        "short":       True,
        "api":         False,
        "env_keys":    [],
        "note":        "Long-term prop account. Manual — Sage tracks setups.",
        "account_sub": "long_term",
    },
}


def _is_connected(account_key: str) -> bool:
    info = ACCOUNTS.get(account_key, {})
    if not info.get("api"):
        return True  # manual accounts always available
    return all(bool(os.getenv(k, "")) for k in info.get("env_keys", []))


def get_available_accounts() -> list:
    result = []
    for key, info in ACCOUNTS.items():
        result.append({
            "key":         key,
            "name":        info["name"],
            "type":        info["type"],
            "connected":   _is_connected(key),
            "leverage":    info["leverage"],
            "short":       info["short"],
            "note":        info["note"],
            "account_sub": info.get("account_sub", ""),
        })
    return result


def get_accounts_message() -> str:
    """Human-readable list Sage speaks when user doesn't specify an account."""
    accounts = get_available_accounts()

    api_accounts    = [a for a in accounts if "manual" not in a["type"]]
    manual_accounts = [a for a in accounts if "manual" in a["type"]]

    lines = []
    for a in api_accounts:
        status = "connected" if a["connected"] else "not connected"
        extras = []
        if a["type"] == "paper":
            extras.append("paper money")
        if a["leverage"]:
            extras.append("leverage")
        if a["short"]:
            extras.append("shorts")
        extra = " (" + ", ".join(extras) + ")" if extras else ""
        lines.append(a["name"] + extra + " — " + status)

    prop_names = [a["name"].replace("Breakout Prop — ", "") for a in manual_accounts]
    lines.append("Breakout Prop — 3 accounts: " + ", ".join(prop_names) + " (manual)")

    return (
        "I see " + str(len(accounts)) + " trading accounts. "
        + " | ".join(lines)
        + ". Which account, Captain? "
        + "For Breakout Prop, also tell me which one: scalp, intermediate, or long term."
    )


def resolve_account(text: str) -> str:
    """
    Parse user's account choice from natural speech.
    Returns account key or '' if unclear.
    """
    t = text.lower()

    # Breakout Prop sub-accounts — check these FIRST before generic "prop"
    if any(w in t for w in ["scalp", "scalping", "scalp account"]):
        return "breakout_prop_scalp"
    if any(w in t for w in ["intermediate", "swing", "interm"]):
        return "breakout_prop_interm"
    if any(w in t for w in ["long term", "longterm", "long-term", "long account", "position trade"]):
        return "breakout_prop_long"

    # API accounts
    if any(w in t for w in ["alpaca", "paper", "paper trading", "test account"]):
        return "alpaca"
    if any(w in t for w in ["bitunix", "bit unix", "unix", "futures"]):
        return "bitunix"
    if any(w in t for w in ["coinbase", "coin base"]):
        return "coinbase"
    if any(w in t for w in ["kraken"]):
        return "kraken"

    # Generic prop — needs clarification
    if any(w in t for w in ["breakout", "prop", "prop firm", "manual"]):
        return "breakout_prop_UNCLEAR"  # caller should ask which sub-account

    return ""


def needs_prop_clarification(account_key: str) -> bool:
    return account_key == "breakout_prop_UNCLEAR"


def build_trade_confirmation(account_key: str, symbol: str, side: str,
                              notional_usd: float = None, qty: float = None,
                              leverage: int = None, stop_pct: float = 1.0,
                              take_profit_pct: float = None) -> str:
    info      = ACCOUNTS.get(account_key, {})
    acct_name = info.get("name", account_key)
    direction = "long" if side.lower() in ("buy", "long") else "short"

    parts = [acct_name, direction, symbol.upper()]

    if notional_usd:
        parts.append("${:.0f}".format(notional_usd))
    elif qty:
        parts.append(str(qty) + " coins")

    if leverage and leverage > 1:
        parts.append("{}x leverage".format(leverage))
        if notional_usd:
            parts.append("(~${:.0f} position)".format(notional_usd * leverage))

    parts.append("{:.0f}% stop loss".format(stop_pct))

    if take_profit_pct:
        parts.append("{:.0f}% take profit".format(take_profit_pct))

    is_manual = "manual" in info.get("type", "")
    suffix = " Say yes and I'll log it, Captain." if is_manual else " Say yes to execute, Captain."
    return "Confirm: " + ", ".join(parts) + "." + suffix


def get_status() -> dict:
    accounts  = get_available_accounts()
    connected = [a["name"] for a in accounts if a["connected"]]
    pending   = [a["name"] for a in accounts if not a["connected"]]
    return {
        "success":   True,
        "accounts":  accounts,
        "connected": connected,
        "pending":   pending,
        "message":   (
            "Trading router: "
            + str(len(connected)) + " available ("
            + ", ".join(connected) + "). "
            + (str(len(pending)) + " need setup: " + ", ".join(pending) + "." if pending else "")
        ),
    }
