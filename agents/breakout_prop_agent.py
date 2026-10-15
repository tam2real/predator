"""
breakout_prop_agent.py -- Breakout Prop Firm Agent
Three manual prop accounts: scalp, intermediate, long_term.
No API — Sage tracks setups, checks rules, logs trades you report to it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import shared_state

AGENT_NAME = "breakout_prop"

ACCOUNT_LABELS = {
    "scalp":        "Breakout Prop Scalp",
    "intermediate": "Breakout Prop Intermediate",
    "long_term":    "Breakout Prop Long Term",
}

# Risk rules per account type
ACCOUNT_RULES = {
    "scalp": {
        "max_risk_pct": 0.5,
        "min_rr":       1.5,
        "style":        "scalp — quick in and out, tight stops",
    },
    "intermediate": {
        "max_risk_pct": 1.0,
        "min_rr":       2.0,
        "style":        "swing/intermediate — hold hours to days",
    },
    "long_term": {
        "max_risk_pct": 2.0,
        "min_rr":       3.0,
        "style":        "long-term position — hold days to weeks",
    },
}


def _label(account_sub: str) -> str:
    return ACCOUNT_LABELS.get(account_sub, "Breakout Prop (" + account_sub + ")")


def log_trade(symbol: str, side: str, entry: float, stop: float,
              take_profit: float, account_sub: str = "scalp",
              size: float = None, notes: str = "") -> dict:
    """Log a manual prop trade."""
    label    = _label(account_sub)
    task_key = label + " — " + symbol
    shared_state.update_agent(AGENT_NAME, status="running", current_task="Logging " + task_key)

    risk_pct = abs((stop - entry) / entry * 100) if entry else 0
    rr       = abs((take_profit - entry) / (entry - stop)) if (entry - stop) != 0 else 0

    msg = (
        "{label} trade logged: {side} {sym} at ${entry:.2f}. "
        "Stop ${stop:.2f} ({risk:.2f}% risk), target ${tp:.2f} ({rr:.1f}R). "
        "{notes}"
    ).format(
        label=label, side=side.upper(), sym=symbol.upper(),
        entry=entry, stop=stop, risk=risk_pct,
        tp=take_profit, rr=rr,
        notes=notes if notes else "",
    )

    shared_state.update_agent(AGENT_NAME, status="done",
                              last_success=task_key + " " + side + " logged")
    return {
        "success":      True,
        "account":      "breakout_prop",
        "account_sub":  account_sub,
        "label":        label,
        "symbol":       symbol,
        "side":         side,
        "entry":        entry,
        "stop":         stop,
        "take_profit":  take_profit,
        "risk_pct":     risk_pct,
        "risk_reward":  rr,
        "message":      msg,
    }


def review_setup(symbol: str, entry: float, stop: float,
                 take_profit: float, account_sub: str = "scalp") -> dict:
    """Evaluate a prop setup — checks against that account's specific rules."""
    label    = _label(account_sub)
    rules    = ACCOUNT_RULES.get(account_sub, ACCOUNT_RULES["intermediate"])

    risk_pct = abs((stop - entry) / entry * 100) if entry else 0
    rr       = abs((take_profit - entry) / (entry - stop)) if (entry - stop) != 0 else 0

    warnings = []
    if risk_pct > rules["max_risk_pct"]:
        warnings.append(
            "Risk {:.2f}% exceeds the {:.1f}% max for this account.".format(
                risk_pct, rules["max_risk_pct"])
        )
    if rr < rules["min_rr"]:
        warnings.append(
            "R:R is {:.1f} — this account targets {:.1f}R minimum.".format(
                rr, rules["min_rr"])
        )

    quality  = "solid" if not warnings else "needs work"
    warn_str = " Warning: " + " ".join(warnings) if warnings else ""

    msg = (
        "{label} setup on {sym}: entry ${entry:.2f}, stop ${stop:.2f} "
        "({risk:.2f}% risk), target ${tp:.2f} ({rr:.1f}R). "
        "Setup looks {q} for {style}.{w}"
    ).format(
        label=label, sym=symbol.upper(),
        entry=entry, stop=stop, risk=risk_pct,
        tp=take_profit, rr=rr, q=quality,
        style=rules["style"], w=warn_str,
    )

    shared_state.update_agent(AGENT_NAME, status="done")
    return {
        "success":     True,
        "account":     "breakout_prop",
        "account_sub": account_sub,
        "label":       label,
        "symbol":      symbol,
        "risk_pct":    risk_pct,
        "risk_reward": rr,
        "warnings":    warnings,
        "message":     msg,
    }


def get_rules(account_sub: str = "scalp") -> dict:
    """Return rules for a specific prop account."""
    label = _label(account_sub)
    rules = ACCOUNT_RULES.get(account_sub, ACCOUNT_RULES["intermediate"])
    lines = [
        "Style: " + rules["style"],
        "Max risk per trade: " + str(rules["max_risk_pct"]) + "%",
        "Minimum R:R: " + str(rules["min_rr"]) + "R",
        "Always set a stop loss before entry.",
        "Log every trade — wins and losses both.",
        "Check your daily drawdown limit on the dashboard before trading.",
    ]
    msg = label + " rules: " + " | ".join(lines)
    return {"success": True, "account": "breakout_prop", "account_sub": account_sub,
            "label": label, "rules": lines, "message": msg}


def get_all_accounts() -> dict:
    """List all three prop accounts and their status."""
    msg = (
        "You have 3 Breakout Prop accounts: "
        "Scalp (tight stops, 1.5R min, 0.5% max risk), "
        "Intermediate (swing trades, 2R min, 1% max risk), "
        "Long Term (position trades, 3R min, 2% max risk). "
        "Which one, Captain?"
    )
    return {"success": True, "account": "breakout_prop", "message": msg}


def get_status() -> dict:
    state = shared_state.get_agent(AGENT_NAME)
    state["mode"]     = "manual"
    state["exchange"] = "breakout_prop"
    state["accounts"] = ["scalp", "intermediate", "long_term"]
    state["api"]      = "none — manual tracking only"
    return state
