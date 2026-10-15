"""
Predator Signal Engine — entry/stop/target + R:R from market structure + volume.
"""
import json
from pathlib import Path
from datetime import datetime

SIGNALS_PATH = Path(__file__).parent / "data" / "signals.json"

def load_signals():
    if not SIGNALS_PATH.exists():
        return {"signals": [], "last_updated": None}
    with open(SIGNALS_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_signals(data):
    data["last_updated"] = datetime.utcnow().isoformat()
    with open(SIGNALS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_signal(symbol, price, structure, volume, support, resistance):
    entry = float(price)
    sup = float(support[0]) if support else entry * 0.96
    res = float(resistance[0]) if resistance else entry * 1.12
    direction = "long" if structure == "higher_highs" else "short"
    # For short, flip stop/target
    if direction == "short":
        stop, target = res, sup
    else:
        stop, target = sup, res
    # ensure stop is on correct side
    if direction == "long" and stop >= entry:
        stop = entry * 0.97
    if direction == "short" and stop <= entry:
        stop = entry * 1.03
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = round(reward / risk, 2) if risk > 0 else 0
    confidence = 5
    if structure == "higher_highs" and volume and volume > 1_000_000:
        confidence = 8
    elif structure == "higher_highs":
        confidence = 6
    elif structure == "lower_lows":
        confidence = 4
    return {
        "symbol": symbol.upper(),
        "price": entry,
        "structure": structure,
        "volume": volume,
        "support": support,
        "resistance": resistance,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr_ratio": rr,
        "confidence": confidence,
        "status": "active",
        "timestamp": datetime.utcnow().isoformat(),
    }

def add_signal(signal):
    data = load_signals()
    data["signals"].append(signal)
    save_signals(data)
    return signal

def get_active_signals():
    data = load_signals()
    return [s for s in data.get("signals", []) if s.get("status") == "active"]

def close_signal(symbol, reason="closed"):
    data = load_signals()
    for s in data.get("signals", []):
        if s.get("symbol") == symbol.upper() and s.get("status") == "active":
            s["status"] = reason
            s["closed_at"] = datetime.utcnow().isoformat()
    save_signals(data)

if __name__ == "__main__":
    s = generate_signal("BTC", 65000, "higher_highs", 2000000, [64000], [67000])
    print(json.dumps(s, indent=2))
    add_signal(s)
    print("active:", len(get_active_signals()))
