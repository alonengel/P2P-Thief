"""Strategy-layer tunables: [deception] defaults for the thief posture.

Private, per-peer knobs - never signed game terms. Kept beside the loader
rather than inside it so the shipped posture is readable in one place and the
loader stays a loader; the twin repo carries the same module with the cop's
own tables and defaults (the values legitimately differ by role).
"""

DECEPTION_DEFAULTS: dict = {
    "max_lies": 3,                 # a small budget, spent only when hunted
    "cooldown_turns": 4,           # minimum full turns between lies
    "exposure_threshold": 0.35,    # mirror mass near our true cell that arms a lie
    "opponent_distance_threshold": 3,  # believed hunter distance that arms a lie
    "exposure_radius": 1,          # Manhattan radius of the exposure mass
    "baseline_truth_probability": 0.5,
}
# Deception-by-movement (leakage-aware move scoring). The shipped default
# follows results/experiments/movement_deception.json.
MOVEMENT_DEFAULTS: dict = {
    "enabled": True,
    "blend_weight": 8.0,
    "safe_distance": 3,            # flee-term cap: stealth governs past this
    "exposure_radius": 1,
}


def _merge(defaults: dict, block: dict) -> dict:
    """Block over defaults, coercing to the default's type so a TOML int never
    silently changes a float comparison."""
    merged = dict(defaults)
    for key, default in defaults.items():
        if key in block:
            merged[key] = type(default)(block[key])
    return merged


def deception_table(private: dict) -> dict:
    """[deception] + its [deception.movement] sub-table, defaults filled in."""
    block = private.get("deception", {})
    return {**_merge(DECEPTION_DEFAULTS, block),
            "movement": _merge(MOVEMENT_DEFAULTS, block.get("movement", {}))}
