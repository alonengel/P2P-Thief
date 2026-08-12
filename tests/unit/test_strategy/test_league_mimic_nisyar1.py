"""Adaptive nis-yar1 cop mimic — the live bar for the room-first thief.

Open-loop tapes underestimate a REACTIVE herder (it chases where we are, not
where a recording went), so this mimic rebuilds their cop's observed shape
from the 2026-08-11 kill games and STRENGTHENS it: BFS chase on true
position, fewest-exit seal inside gap 2, and the rule-46 kill-wall their
real cop has never used. Claim-silent, landmark-lying prose — the quiet
regime that killed the pre-fix thief at 13 turns, three games straight.
Measured at ship time: 30/30 survivals (pre-fix: 0/3 live).
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
        "Heading straight for Times Square, no detours this time.",
        "The wind changes faster than your plans.",
        "I am circling Grand Central until sunrise.",
        "Every alley whispers my name and none of them repeat it.",
        "Your footsteps echo; mine never do."]


class HerderMimic:
    """Chase + fewest-exit seal + rule-46 kill-wall, all on TRUE position."""

    def __init__(self) -> None:
        self.left = RULES.max_barriers

    def act(self, engine) -> dict:
        me = engine.positions[Role.POLICE]
        thief = engine.positions[Role.THIEF]
        dist = bfs_distances(engine.board, thief)
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
                return {"type": "barrier", "cell": [cell[0], cell[1]]}
            if thief in legal:
                self.left -= 1
                return {"type": "barrier", "cell": [thief[0], thief[1]]}
        chase = min(engine.board.legal_moves(me),
                    key=lambda m: dist.get(m.applied_to(me), 99))
        return {"type": "move", "move": chase.name}


def _play(seed: int) -> Outcome:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief = ThiefBrain(Role.THIEF, random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, Config.load("config"))
    cop, turn = HerderMimic(), 0
    while engine.outcome is Outcome.ONGOING and turn < RULES.max_moves:
        turn += 1
        action = cop.act(engine)
        barrier = tuple(action["cell"]) if action["type"] == "barrier" else None
        try:
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, LIES[turn % len(LIES)],
                       barrier_cell=barrier, claim_cell=None)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, percep.belief))
    return engine.outcome


def test_room_first_thief_survives_the_adaptive_herder() -> None:
    survivals = sum(_play(seed) is Outcome.SURVIVAL for seed in range(10))
    assert survivals >= 9, f"herder mimic: only {survivals}/10 survived"


class MetronomeCop:
    """Their live cadence, exactly as the moves reports measured it across
    every kill: approach to gap 2, HOLD (never closes to 1), first wall at
    turn 9, fewest-exit seals after. Its only conversion is a pocketed
    thief — room-first starves it completely (15/15 at ship time)."""

    def __init__(self) -> None:
        self.left = RULES.max_barriers

    def act(self, engine, turn: int) -> dict:
        me = engine.positions[Role.POLICE]
        thief = engine.positions[Role.THIEF]
        dist = bfs_distances(engine.board, thief)
        gap = dist.get(me, 99)
        if turn >= 9 and self.left > 0 and gap <= 2:
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
                return {"type": "barrier", "cell": [cell[0], cell[1]]}
        if gap <= 2:
            return {"type": "move", "move": "STAY"}
        chase = min(engine.board.legal_moves(me),
                    key=lambda m: dist.get(m.applied_to(me), 99))
        return {"type": "move", "move": chase.name}


def _play_metronome(seed: int) -> Outcome:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief = ThiefBrain(Role.THIEF, random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, Config.load("config"))
    cop, turn = MetronomeCop(), 0
    while engine.outcome is Outcome.ONGOING and turn < RULES.max_moves:
        turn += 1
        action = cop.act(engine, turn)
        barrier = tuple(action["cell"]) if action["type"] == "barrier" else None
        try:
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, LIES[turn % len(LIES)],
                       barrier_cell=barrier, claim_cell=None)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, percep.belief))
    return engine.outcome


def test_the_metronome_cop_cannot_convert_us_at_all() -> None:
    """The exploit, pinned as a guarantee: their observed kill cadence has
    exactly one conversion path (herd -> pocket -> seal) and the room-first
    thief refuses pockets. Zero deaths tolerated on the fixed seeds."""
    survivals = sum(_play_metronome(seed) is Outcome.SURVIVAL for seed in range(15))
    assert survivals == 15, f"metronome cop converted us: {survivals}/15"
