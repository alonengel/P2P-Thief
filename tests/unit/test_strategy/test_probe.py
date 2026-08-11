"""Probe thief: waypoint tour, dwell, dodge — and never a truth read."""

import random
from types import SimpleNamespace

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.brain_base import resolve_brain
from p2p_thief.strategy.probe import ProbeThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def _cfg(waypoints, dwell=2):
    return SimpleNamespace(private={"strategy": {
        "thief_class": "p2p_thief.strategy.probe:ProbeThiefBrain",
        "probe": {"waypoints": waypoints, "dwell_turns": dwell}}})


def _far_belief() -> BeliefMap:
    belief = BeliefMap(7)
    belief.observe_claimed_cell((0, 0))
    return belief


def test_probe_walks_the_tour_and_dwells() -> None:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    brain = ProbeThiefBrain(Role.THIEF, random.Random(0), config=_cfg([[3, 5]], dwell=2))
    seen = []
    for _ in range(6):
        engine.police_move(Move.STAY)                # cop half-turn first
        action = brain.decide(engine, _far_belief())
        seen.append(action["move"])
        engine.thief_move(Move[action["move"]])
    assert engine.positions[Role.THIEF] == (3, 5)   # reached the stop
    assert seen.count("STAY") >= 2                   # and dwelt there


def test_probe_dodges_an_adjacent_believed_cop() -> None:
    engine = GameEngine(7, (3, 4), (3, 3), RULES)   # cop truly adjacent
    belief = BeliefMap(7)
    belief.observe_claimed_cell((3, 4))
    brain = ProbeThiefBrain(Role.THIEF, random.Random(0), config=_cfg([[3, 5]]))
    action = brain.decide(engine, belief)
    assert action["move"] not in ("STAY", "E")       # not toward the threat


def test_probe_is_seam_selectable() -> None:
    picked = resolve_brain(_cfg([[1, 1]]), Role.THIEF, random.Random(0))
    assert type(picked) is ProbeThiefBrain
    assert picked.stops == [(1, 1)]
