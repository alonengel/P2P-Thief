"""Belief-native wall forecast: the parent's one-ply worst-wall probe runs
in belief play as a MIN over the TOP-K support cells — a split posterior can
aim the lone argmax wrong, and a kill line through ANY plausible hunter cell
must disqualify a landing. Keep-if-better gated ([strategy.doctrine])."""

import random
from types import SimpleNamespace

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.domain.scent import ScentField
from p2p_thief.strategy.doctrine import DEFAULTS, DoctrineThiefBrain, top_support

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
STEALTH = {"enabled": True, "blend_weight": 8.0, "safe_distance": 3, "exposure_radius": 1}
OFF = {**DEFAULTS, "fresh_flee": False, "stay_cap": False, "pocket_escape": False,
       "forecast": False}


def test_top_support_ranks_mass_deterministically() -> None:
    belief = BeliefMap(7)
    scent = ScentField(7)
    scent.update((4, 4))
    belief.observe_scent(scent, GameEngine(7, (0, 0), (6, 6), RULES).board)
    support = top_support(belief, 3)
    assert len(support) == 3 and support[0] == belief.argmax_cell()
    assert len(set(support)) == 3  # distinct cells, mass-ordered


def test_top_support_reads_any_belief_shaped_view() -> None:
    stub = SimpleNamespace(values=lambda: [[0.0, 0.7], [0.3, 0.0]])
    assert top_support(stub, 2) == [(0, 1), (1, 0)]
    assert top_support(stub, 5) == [(0, 1), (1, 0)]  # zero cells never rank


def test_forecast_min_over_support_dodges_the_wallable_landing() -> None:
    # A one-ply wall threat scored ONLY at the argmax misses the hunter's
    # other plausible cells. Two-peak belief: argmax far at (5,5), residual
    # support in the (1,0) corner pocket. From (0,1) every landing except E
    # can be slammed by a support cell's legal wall (rule 46 on our cell);
    # the MIN over the top-k support must steer E, the argmax alone cannot.
    engine = GameEngine(7, (6, 6), (0, 1), RULES)
    belief = BeliefMap(7)
    readings = {(5, 5): 0.9, (1, 0): 0.81}
    stub = SimpleNamespace(
        value_at=lambda cell: readings.get(cell, 0.0),
        values=lambda: [[readings.get((r, c), 0.0) for c in range(7)] for r in range(7)],
    )
    belief.observe_scent(stub, engine.board)
    assert belief.argmax_cell() == (5, 5)
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(17), tuning=STEALTH,
                               doctrine={**OFF, "forecast": True})
    for seed in range(5):
        brain.rng = random.Random(seed)  # candidate order must not matter
        action = brain.decide(engine, belief)
        assert action["move"] == "E", f"walked into the wallable pocket: {action}"
