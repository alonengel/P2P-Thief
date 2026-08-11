"""Decoy thief: friendlies show the herdable shape, counted ships the fix."""

import random
from types import SimpleNamespace

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.brain_base import resolve_brain
from p2p_thief.strategy.decoy import DecoyThiefBrain
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def _belief_on(cell, grid=7) -> BeliefMap:
    belief = BeliefMap(grid)
    belief.observe_claimed_cell(cell)
    return belief


def test_decoy_parks_in_the_corner_the_real_brain_refuses() -> None:
    """The exact live kill geometry (thief (6,6), cop believed (5,5)): the
    fixed brain flees; the decoy sits — that IS the shape rivals tuned on."""
    engine = GameEngine(7, (5, 5), (6, 6), RULES)
    decoy = DecoyThiefBrain(Role.THIEF, random.Random(0)).decide(engine, _belief_on((5, 5)))
    real = ThiefBrain(Role.THIEF, random.Random(0)).decide(engine, _belief_on((5, 5)))
    assert decoy["move"] == "STAY"          # herdable, deliberately
    assert real["move"] != "STAY"           # the counted brain leaves

    engine2 = GameEngine(7, (5, 5), (6, 6), RULES)
    exact = DecoyThiefBrain(Role.THIEF, random.Random(0)).decide(engine2, None)
    assert exact["type"] == "move"          # exact-info play stays the real one


def test_overlay_seam_selects_the_decoy_and_defaults_to_the_real_brain() -> None:
    decoy_cfg = SimpleNamespace(private={"strategy": {
        "thief_class": "p2p_thief.strategy.decoy:DecoyThiefBrain"}})
    picked = resolve_brain(decoy_cfg, Role.THIEF, random.Random(0))
    assert type(picked) is DecoyThiefBrain
    bare = resolve_brain(SimpleNamespace(private={}), Role.THIEF, random.Random(0))
    assert not isinstance(bare, DecoyThiefBrain)
