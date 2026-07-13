"""PRD-04 MILESTONE: the belief map, not luck, drives the moves - a cop that
only ever sees the thief's scent field and (half-lying) hints still hunts."""

import random

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.brain_base import RandomBrain
from p2p_thief.strategy.hints import build_hint, parse_claim
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def play_blind(seed: int) -> Outcome:
    rng = random.Random(seed)
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    cop = RandomBrain(Role.POLICE, random.Random(seed + 500))
    thief = ThiefBrain(Role.THIEF, rng)
    belief = BeliefMap(7)
    while engine.outcome is Outcome.ONGOING:
        action = cop.decide(engine)
        protocol.apply_action(engine, Role.POLICE, action)
        if engine.outcome is not Outcome.ONGOING:
            break
        # the thief's senses: cop scent + a half-honest hint - never the truth
        text, _, _ = build_hint(Move[action["move"]], rng.random() < 0.5, 15, rng)
        belief.diffuse(engine.board)
        belief.observe_scent(engine.scent[Role.POLICE], engine.board)
        claim = parse_claim(text)
        if claim:
            belief.observe_hint(claim, engine.scent[Role.POLICE])
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, belief))
    return engine.outcome


def test_belief_driven_thief_still_evades_random_cop() -> None:
    survivals = sum(play_blind(seed) is Outcome.SURVIVAL for seed in range(25))
    assert survivals >= 15, f"blind thief survived only {survivals}/25"
