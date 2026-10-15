"""
Predator Risk Manager — BreakoutProp rules (1% per trade, 5% daily, 10% total).
Daily usage is read from Gaze closed-positions if available.
"""
import json
from pathlib import Path
from datetime import datetime

RISK_LIMITS_PATH = Path(__file__).parent / "data" / "risk-limits.json"
# Gaze integration: daily usage from closed positions
GAZE_CLOSED_PATH = Path(__file__).parent.parent.parent / "gaze" / "position-tracker" / "data" / "closed-positions.json"

def load_limits():
    with open(RISK_LIMITS_PATH, encoding="utf-8") as f:
        return json.load(f)

def get_daily_usage():
    """Sum today's closed P&L losses from Gaze (negative pnl = loss)."""
    if not GAZE_CLOSED_PATH.exists():
        return 0
    try:
        data = json.loads(GAZE_CLOSED_PATH.read_text(encoding="utf-8"))
        today = datetime.utcnow().date().isoformat()
        total_loss = 0
        for p in data.get("positions", []):
            closed_at = (p.get("closed_at") or "")[:10]
            if closed_at == today and p.get("pnl", 0) < 0:
                total_loss += abs(float(p["pnl"]))
        return total_loss
    except Exception:
        return 0

def get_daily_profit():
    """Sum today's closed P&L GAINS from Gaze (positive pnl = gain).

    Same source as get_daily_usage() so the two sides of the day can never
    disagree about which trades count. Open positions are deliberately NOT
    counted: the chairman's rule is that reaching the take-profit target does
    NOT close positions — a runner is allowed to keep going.
    """
    if not GAZE_CLOSED_PATH.exists():
        return 0
    try:
        data = json.loads(GAZE_CLOSED_PATH.read_text(encoding="utf-8"))
        today = datetime.utcnow().date().isoformat()
        gain = 0
        for p in data.get("positions", []):
            closed_at = (p.get("closed_at") or "")[:10]
            if closed_at == today and p.get("pnl", 0) > 0:
                gain += float(p["pnl"])
        return gain
    except Exception:
        return 0


def get_protect_mode(limits=None):
    """Is the city protected today, and why.

    Returns which limit was hit. `trading_allowed` is the single gate every
    entry check must read — halt_new_entries means existing positions keep
    being managed and their stops keep moving, but nothing NEW opens.
    """
    limits = limits or load_limits()
    acct = float(limits.get("account_size", 10000))
    used = get_daily_usage()
    profit = get_daily_profit()
    daily_limit = acct * float(limits.get("daily_loss_limit_pct", 5)) / 100
    tp_pct = limits.get("daily_take_profit_pct")
    tp_mode = str(limits.get("take_profit_mode", "auto")).lower()
    if tp_mode == "manual" and tp_pct not in (None, ""):
        tp = acct * float(tp_pct) / 100
    else:
        tp = daily_limit * float(limits.get("take_profit_ratio", 3) or 3)

    hit_loss = used >= daily_limit
    hit_profit = profit >= tp

    if hit_loss:
        reason = "daily_loss_limit"
    elif hit_profit:
        reason = "daily_take_profit"
    else:
        reason = None

    cfg = limits.get("protect_mode") or {}
    return {
        "protect_mode": bool(reason) if cfg.get("enabled", True) else False,
        "reason": reason,
        "trading_allowed": reason is None,
        "new_entries_allowed": reason is None,
        "existing_positions_managed": True,   # never abandoned, stops keep moving
        "tighten_stops": bool(cfg.get("tighten_stops_on_protect", True)) and reason is not None,
        "resets": cfg.get("reset", "next_trading_day"),
        "daily_profit": round(profit, 2),
        "daily_take_profit": round(tp, 2),
        "daily_profit_remaining": round(max(0.0, tp - profit), 2),
    }


def check_trade(symbol, direction, size, stop, entry):
    limits = load_limits()
    size = float(size)
    entry = float(entry)
    stop = float(stop)
    risk_per_unit = abs(entry - stop)
    total_risk = risk_per_unit * size
    acct = float(limits.get("account_size", 10000))
    risk_pct = (total_risk / acct) * 100 if acct else 0
    max_pct = float(limits.get("max_risk_per_trade_pct", 1))
    if risk_pct > max_pct:
        return {"safe": False, "reason": f"Risk {risk_pct:.2f}% exceeds max {max_pct}%", "risk_amount": round(total_risk, 2), "risk_pct": round(risk_pct, 2)}
    daily_used = get_daily_usage()
    daily_limit = acct * float(limits.get("daily_loss_limit_pct", 5)) / 100
    if daily_used + total_risk > daily_limit:
        return {"safe": False, "reason": "Daily loss limit would be exceeded", "risk_amount": round(total_risk, 2), "risk_pct": round(risk_pct, 2), "daily_used": round(daily_used, 2), "daily_limit": round(daily_limit, 2)}
    return {"safe": True, "reason": "Trade is within risk limits", "risk_amount": round(total_risk, 2), "risk_pct": round(risk_pct, 2), "daily_used": round(daily_used, 2), "daily_remaining": round(daily_limit - daily_used, 2)}

def get_status():
    limits = load_limits()
    acct = float(limits.get("account_size", 10000))
    daily_used = get_daily_usage()
    daily_limit = acct * float(limits.get("daily_loss_limit_pct", 5)) / 100
    total_limit = acct * float(limits.get("total_drawdown_limit_pct", 10)) / 100

    # Take-profit has two sources, and which one wins must be explicit:
    #
    #   auto   — follow the loss limit at the ratio (the 1:3 he trades to), so
    #            setting risk 200 gives TP 600 automatically
    #   manual — he set a number, and it stands even if risk moves later
    #
    # Without the mode flag an explicit TP was frozen at whatever it was when
    # it was written, so lowering the risk left the target stranded. That is
    # exactly the "must track" behaviour he asked for.
    tp_pct = limits.get("daily_take_profit_pct")
    tp_mode = str(limits.get("take_profit_mode", "auto")).lower()
    if tp_mode == "manual" and tp_pct not in (None, ""):
        tp = acct * float(tp_pct) / 100
    else:
        tp = daily_limit * float(limits.get("take_profit_ratio", 3) or 3)
    protect = get_protect_mode(limits)

    return {
        "daily_used": round(daily_used, 2),
        "daily_remaining": round(daily_limit - daily_used, 2),
        "daily_limit": round(daily_limit, 2),
        "daily_profit": protect["daily_profit"],
        "daily_take_profit": round(tp, 2),
        "daily_profit_remaining": protect["daily_profit_remaining"],
        "daily_profit_limit_pct": tp_pct,
        "take_profit_mode": tp_mode,
        "take_profit_ratio": float(limits.get("take_profit_ratio", 3) or 3),
        "protect_mode": protect["protect_mode"],
        "protect_reason": protect["reason"],
        "trading_allowed": protect["trading_allowed"],
        "new_entries_allowed": protect["new_entries_allowed"],
        "existing_positions_managed": protect["existing_positions_managed"],
        "tighten_stops": protect["tighten_stops"],
        "protect_resets": protect["resets"],
        "total_used": 0,
        "total_remaining": round(total_limit, 2),
        "total_limit": round(total_limit, 2),
        "account_size": acct,
        "max_risk_per_trade_pct": limits.get("max_risk_per_trade_pct"),
        "updated": datetime.utcnow().isoformat(),
    }

if __name__ == "__main__":
    print(json.dumps(check_trade("BTC", "long", 0.1, 64000, 65000), indent=2))
    print(json.dumps(get_status(), indent=2))
