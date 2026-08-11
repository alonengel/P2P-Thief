"""Decoy thief for FRIENDLY sparring only — yesterday's runner, on purpose.

League rivals tune against whatever we show them in friendlies. nis-yar1's
cop was rebuilt around herding a distance-first thief into a corner seal
(three identical 13-turn kills, 2026-08-11); our fixed thief scores room
before range and breaks that kill. Every friendly the fixed thief plays is
free tape for their next counter — so friendlies can field THIS decoy: the
pre-fix distance-first scorer, bit for bit the shape their seal already
beats. Let them keep believing the seal works.

Selection is config-only (never code): the FRIENDLY overlay sets
    [strategy]
    thief_class = "p2p_thief.strategy.decoy:DecoyThiefBrain"
and the counted overlay leaves [strategy] unset, which ships the real brain.
Friendlies are uncounted practice — no rule governs how strong a practice
opponent must be, and every sealed record stays honest either way.
"""

from p2p_thief.domain.pathfind import UNREACHABLE
from p2p_thief.domain.primitives import Move
from p2p_thief.strategy.thief_brain import ThiefBrain


class DecoyThiefBrain(ThiefBrain):
    """ThiefBrain with the pre-fix blind scorer: distance first, room last."""

    def _score(self, engine, cell, distances, cop, exact):
        if exact:
            return super()._score(engine, cell, distances, cop, exact)
        distance = distances.get(cell, UNREACHABLE)
        if distance == UNREACHABLE:
            distance = 10**6
        openness = sum(1 for m in (Move.N, Move.S, Move.E, Move.W)
                       if engine.board.is_passable(m.applied_to(cell)))
        return (distance, openness)  # the herdable shape, preserved on purpose
