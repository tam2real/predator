"""
Predator Daily Briefing — real scan + Gaze positions + risk status.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

TEMPLATE_PATH = Path(__file__).parent / "templates" / "morning-briefing.txt"
SCANNER_PATH = Path(__file__).parent.parent / "market-scanner" / "scanner.py"
GAZE_OPEN_PATH = Path(__file__).parent.parent.parent / "gaze" / "position-tracker" / "data" / "open-positions.json"
GAZE_CLOSED_PATH = Path(__file__).parent.parent.parent / "gaze" / "position-tracker" / "data" / "closed-positions.json"
RISK_LIMITS_PATH = Path(__file__).parent.parent / "risk-manager" / "data" / "risk-limits.json"

def load_scan():
    try:
        # reuse scanner logic without re-fetching if scan file recent; else call scan()
        scans_dir = Path(__file__).parent.parent / "market-scanner" / "data" / "scans"
        if scans_dir.exists():
            files = sorted(scans_dir.glob("scan-*.json"))
            if files:
                # use newest if <1h old
                latest = files[-1]
                age = (datetime.utcnow().timestamp() - latest.stat().st_mtime)
                if age < 3600:
                    return json.loads(latest.read_text(encoding="utf-8"))
        # fallback: import scanner.scan
        sys.path.insert(0, str(Path(__file__).parent.parent / "market-scanner"))
        import scanner as pred_scanner
        data = pred_scanner.scan()
        return data.get("setups", data) if isinstance(data, dict) and "setups" in data else data
    except Exception as e:
        return {"error": str(e), "setups": []}

def load_gaze_positions():
    try:
        if GAZE_OPEN_PATH.exists():
            return json.loads(GAZE_OPEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"positions": []}

def load_risk_status():
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "risk-manager"))
        import importlib.util, importlib
        spec = importlib.util.spec_from_file_location("risk_check", str(Path(__file__).parent.parent / "risk-manager" / "risk-check.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.get_status()
    except Exception:
        # fallback reading limits directly
        try:
            limits = json.loads(RISK_LIMITS_PATH.read_text(encoding="utf-8"))
            acct = float(limits.get("account_size", 10000))
            return {"daily_limit": acct * 0.05, "daily_remaining": acct * 0.05, "daily_used": 0, "account_size": acct}
        except Exception:
            return {"daily_limit": 500, "daily_remaining": 500, "daily_used": 0, "account_size": 10000}

def load_template():
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        "=== PREDATOR DAILY BRIEFING {date} ===\n"
        "Market: {market}\n"
        "Top setups:\n{setups}\n"
        "Positions: {positions}\n"
        "P&L: daily {daily_pnl} weekly {weekly_pnl}\n"
        "Risk: {risk_remaining} remaining / {max_daily_risk} daily limit\n"
    )

def format_setups(setups):
    if not setups:
        return "No setups found."
    lines = []
    for i, s in enumerate(setups[:3], 1):
        sym = s.get("symbol", "?")
        sc = s.get("score", "?")
        price = s.get("price", "?")
        try:
            ch = f"{float(s.get('change_24h') or 0):+.2f}"
        except (TypeError, ValueError):
            ch = "0.00"
        lines.append(f"{i}. {sym} ${price} ({ch}% 24h) — score {sc}/10  S:{s.get('support')} R:{s.get('resistance')}")
    return "\n".join(lines)

class _Fmt:
    """Value wrapper that satisfies template format specs like :,.0f / :+.2f even for non-numerics."""
    def __init__(self, v):
        self.v = v
    def __format__(self, spec):
        if not spec:
            return str(self.v)
        try:
            return format(float(self.v), spec)
        except (TypeError, ValueError):
            return str(self.v)

def _first_num(v, default=0):
    if isinstance(v, list):
        v = v[0] if v else default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def generate_briefing():
    scan_data = load_scan()
    setups = scan_data.get("setups") if isinstance(scan_data, dict) else scan_data
    if isinstance(setups, list):
        market = scan_data.get("market", "unknown") if isinstance(scan_data, dict) else "unknown"
    else:
        setups, market = [], "unknown"
    gaze = load_gaze_positions()
    positions = gaze.get("positions", [])
    pos_text = f"{len(positions)} open" if positions else "No open positions"
    if positions:
        pos_text += ": " + ", ".join(f"{p.get('symbol')} {p.get('direction')} pnl {p.get('pnl',0)}" for p in positions[:5])
    risk = load_risk_status()
    # try template.format with rich keys, fallback to simple
    template = load_template()
    try:
        # build kwargs for legacy template (with specific placeholders)
        top = setups[:3] if setups else []
        def g(i, k, d="?"):
            return top[i].get(k, d) if len(top) > i else d
        # legacy morning-briefing.txt expects many keys; supply defaults
        out = template.format(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            market=market,
            setups=format_setups(setups),
            positions=pos_text,
            daily_pnl="$0",
            weekly_pnl="$0",
            monthly_pnl="$0",
            risk_remaining=f"${float(risk.get('daily_remaining', 500) or 0):.0f}",
            max_daily_risk=f"{float(risk.get('daily_limit', 500) or 0):.0f}",
            btc_price=_Fmt(g(0, "price")), btc_change=_Fmt(g(0, "change_24h")), btc_structure="Higher Highs" if market == "bullish" else "Mixed",
            eth_price=_Fmt(g(1, "price")), eth_change=_Fmt(g(1, "change_24h")), eth_structure="Higher Highs",
            setup_1_symbol=g(0, "symbol"), setup_1_direction="LONG", setup_1_entry=_Fmt(g(0, "price")), setup_1_stop=_Fmt(_first_num(g(0, "support"))), setup_1_target=_Fmt(_first_num(g(0, "resistance"))), setup_1_rr="2.0", setup_1_confidence=str(g(0, "score")),
            setup_2_symbol=g(1, "symbol"), setup_2_direction="LONG", setup_2_entry=_Fmt(g(1, "price")), setup_2_stop=_Fmt(_first_num(g(1, "support"))), setup_2_target=_Fmt(_first_num(g(1, "resistance"))), setup_2_rr="2.0", setup_2_confidence=str(g(1, "score")),
            setup_3_symbol=g(2, "symbol"), setup_3_direction="LONG", setup_3_entry=_Fmt(g(2, "price")), setup_3_stop=_Fmt(_first_num(g(2, "support"))), setup_3_target=_Fmt(_first_num(g(2, "resistance"))), setup_3_rr="2.0", setup_3_confidence=str(g(2, "score")),
        )
        return out
    except (KeyError, ValueError, TypeError) as e:
        # template has different keys — return simple briefing
        return f"PREDATOR BRIEFING {datetime.utcnow().strftime('%Y-%m-%d')}\nMarket: {market}\n{format_setups(setups)}\nPositions: {pos_text}\nRisk: ${float(risk.get('daily_remaining',0) or 0):.0f} remaining / ${float(risk.get('daily_limit',0) or 0):.0f} daily\nMissing template key: {e}"

if __name__ == "__main__":
    print(generate_briefing())
