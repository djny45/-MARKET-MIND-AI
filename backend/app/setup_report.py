"""Educational scenario geometry; does not generate signals or execute orders."""
from typing import Literal


def build_setup_report(
    symbol: str,
    direction: Literal["long", "short"],
    entry: float,
    stop: float,
    target: float,
) -> dict:
    """Calculate hypothetical risk/reward geometry from user-supplied levels."""
    if not symbol.strip() or len(symbol.strip()) > 32:
        raise ValueError("symbol must contain 1 to 32 characters")
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")
    if min(entry, stop, target) <= 0:
        raise ValueError("entry, stop, and target must be greater than zero")
    if direction == "long" and not stop < entry < target:
        raise ValueError("for a long scenario, require stop < entry < target")
    if direction == "short" and not target < entry < stop:
        raise ValueError("for a short scenario, require target < entry < stop")

    risk = abs(entry - stop)
    reward = abs(target - entry)
    return {
        "mode": "educational_scenario_only",
        "symbol": symbol.strip().upper(),
        "direction": direction,
        "entry_reference": entry,
        "invalidation_level": stop,
        "target_reference": target,
        "risk_distance": round(risk, 10),
        "reward_distance": round(reward, 10),
        "risk_percent_of_entry": round(risk / entry * 100, 4),
        "reward_percent_of_entry": round(reward / entry * 100, 4),
        "risk_reward_ratio": round(reward / risk, 4),
        "interpretation": "Hypothetical geometry only; not a market signal or recommendation.",
        "execution": "disabled",
    }
