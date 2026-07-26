"""Pure read-only sensors the anti-freeze doctrine scores on.

Split out of doctrine.py so the brain there stays a policy module: these two
functions touch no brain state, take a snapshot view of a scent field or a
belief grid, and answer one question each — is the hunter provably close,
and which cells is it plausibly on. Own-side reads only; the rival's true
position is never available here (guarded by tests/unit/test_rule_guards.py).
"""

from p2p_thief.domain.evidence import decoded_reach


def fresh_evidence(scent, fresh_reach_max: int, near, radius: int) -> bool:
    """Does the rival's trail carry a live (reach<=max) reading close to
    `near`? The rival's OWN vicinity always reads fresh — only freshness
    NEAR US proves the hunter is provably close and arms real flight."""
    values = scent.values()
    return any(
        (reach := decoded_reach(values[row][col])) is not None and reach <= fresh_reach_max
        for row in range(len(values))
        for col in range(len(values[row]))
        if abs(row - near[0]) + abs(col - near[1]) <= radius
    )


def top_support(belief, k: int) -> list:
    """The k highest-mass belief cells, mass-then-cell ordered (mass only
    RANKS the support; the forecast MIN over it is deliberately unweighted —
    a kill line through any plausible cell disqualifies the landing)."""
    values = belief.values()  # snapshot read: works for any belief-shaped view
    cells = sorted(
        (((row, col), mass) for row, masses in enumerate(values)
         for col, mass in enumerate(masses)),
        key=lambda item: (-item[1], item[0]),
    )
    return [cell for cell, mass in cells[:k] if mass > 0.0]
