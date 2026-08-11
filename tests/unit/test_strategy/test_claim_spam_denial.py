"""Claim-spam red team: decoy claims must not steer the belief.

Truth duty binds a capture claim's ANSWER, never the claim itself (book
rules 21-22) — claim cells are free probes. A herder-sealer that spams
mirror-cell decoy claims steered the ungated pin to the far corner and
converted 15/15 survivals into 0/15 (red-team, 2026-08-11). The pin is now
physics-gated: a claim lands only when it agrees with the law-solved trail
emitter, so lying claims bounce off and honest claims still sharpen.
"""

import random

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
LIES = ["I am camped in the shadow of Wall Street tonight.",
        "The wind changes faster than your plans."]


class ClaimSpamSealer:
    """The herder-sealer, tuned: every message claims the MIRROR cell."""

    def __init__(self) -> None:
        self.left = RULES.max_barriers

    def act(self, engine):
        me = engine.positions[Role.POLICE]
        thief = engine.positions[Role.THIEF]
        dist = bfs_distances(engine.board, thief)
        decoy = (6 - me[0], 6 - me[1])
        if self.left > 0 and dist.get(me, 99) <= 2:
            exits = [m.applied_to(thief) for m in (Move.N, Move.S, Move.E, Move.W)
                     if engine.board.is_passable(m.applied_to(thief))
                     and m.applied_to(thief) != me]
            legal = {me} | {m.applied_to(me) for m in (Move.N, Move.S, Move.E, Move.W)}
            seal = [c for c in exits if c in legal]
            if seal:
                cell = min(seal, key=lambda c: sum(
                    1 for m in (Move.N, Move.S, Move.E, Move.W)
                    if engine.board.is_passable(m.applied_to(c))))
                self.left -= 1
                return {"type": "barrier", "cell": [cell[0], cell[1]]}, decoy
        chase = min(engine.board.legal_moves(me),
                    key=lambda m: dist.get(m.applied_to(me), 99))
        return {"type": "move", "move": chase.name}, decoy


def _play(seed: int) -> Outcome:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief = ThiefBrain(Role.THIEF, random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, Config.load("config"))
    cop, turn = ClaimSpamSealer(), 0
    while engine.outcome is Outcome.ONGOING and turn < RULES.max_moves:
        turn += 1
        action, decoy = cop.act(engine)
        barrier = tuple(action["cell"]) if action["type"] == "barrier" else None
        try:
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, LIES[turn % 2],
                       barrier_cell=barrier, claim_cell=decoy)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, percep.belief))
    return engine.outcome


def test_decoy_claims_do_not_steer_the_belief() -> None:
    survivals = sum(_play(seed) is Outcome.SURVIVAL for seed in range(10))
    assert survivals >= 9, f"claim-spam sealer: only {survivals}/10 survived"
