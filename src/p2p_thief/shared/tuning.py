"""Strategy-layer tunables: [deception] defaults for the thief posture.

Private, per-peer knobs - never signed game terms. Kept beside the loader
rather than inside it so the shipped posture is readable in one place and the
loader stays a loader; the twin repo carries the same module with the cop's
own tables and defaults (the values legitimately differ by role).
"""

CLAIM_DEFAULTS: dict = {
    "threshold": 0.10,             # minimum belief mass on our landing cell
    #                                before we DECLARE a capture claim. An
    #                                unconditional claim broadcasts our true
    #                                cell every turn, and a claim-reading
    #                                thief collapses its estimate onto it -
    #                                measured by the rival's own published
    #                                sweep as worth ~24% of cop points. 0.10
    #                                is their measured-best; swept on ours
    #                                once an arena evader reads claims.
}


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


PERCEPTION_DEFAULTS: dict = {
    "floor_tolerance_eps": 0.006,  # residues at/under this may legally read 0
    #                                (najamjad 2026-08-22: their serializer
    #                                floors ~0.005; refusing those frames risks
    #                                a false latch — peer/floor_tolerance.py)
    "rival_scent_law": "book",     # which law verifies the RIVAL's frames.
    #                                "book" = our multiplicative kernel law
    #                                (the only one we can solve). Set "foreign"
    #                                for a pairing whose declared scent model
    #                                is not ours — see peer/floor_tolerance.py.
}


def _merge(defaults: dict, block: dict) -> dict:
    """Block over defaults, coercing to the default's type so a TOML int never
    silently changes a float comparison."""
    merged = dict(defaults)
    for key, default in defaults.items():
        if key in block:
            merged[key] = type(default)(block[key])
    return merged


def perception_table(private: dict) -> dict:
    """[strategy.perception] scent-trust knobs (private, never signed terms)."""
    return _merge(PERCEPTION_DEFAULTS,
                  private.get("strategy", {}).get("perception", {}))


def claim_table(private: dict) -> dict:
    """[strategy.claim] capture-claim gate (private, never a signed term)."""
    return _merge(CLAIM_DEFAULTS, private.get("strategy", {}).get("claim", {}))


def deception_table(private: dict) -> dict:
    """[deception] + its [deception.movement] sub-table, defaults filled in."""
    block = private.get("deception", {})
    return {**_merge(DECEPTION_DEFAULTS, block),
            "movement": _merge(MOVEMENT_DEFAULTS, block.get("movement", {}))}
