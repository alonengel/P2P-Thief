"""Deception by movement: leakage-aware move scoring over the self-mirror.

The estimator PREVIEWS the self-mirror update a candidate landing would
cause — next emission + diffusion on COPIES, never on live state — and
scores flatness: entropy up, mirror mass near our true next cell down.
Measured direction (probe-verified): staying or backtracking onto our own
scent hotspot leaks the most; stepping off a still-hot trail leaves the old
trail behind as a decoy that anchors the rival's posterior away from us.
"""

import random

import pytest

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.domain.scent import ScentField
from p2p_thief.strategy.brain_base import resolve_brain
from p2p_thief.strategy.deception import SelfMirror
from p2p_thief.strategy.movement_deception import (
    LeakageEstimator,
    StealthThiefBrain,
    entropy,
    mass_near,
)
from p2p_thief.strategy.thief_brain import CopForArena, ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
TUNING = {"enabled": True, "blend_weight": 3.0, "safe_distance": 3,
          "exposure_radius": 1}


def make_engine() -> GameEngine:
    return GameEngine(7, (0, 0), (3, 3), RULES)


def drive(mirror: SelfMirror, engine: GameEngine, moves) -> None:
    """Full turns (cop stays, we move); mirror observes post-boundary."""
    for move in moves:
        engine.police_move(Move.STAY)
        engine.thief_move(move)
        mirror.observe_own_turn(engine, None)


def stealth_of(estimator, mirror, engine, move: Move) -> float:
    return estimator.stealth(
        mirror, engine, move.applied_to(engine.positions[Role.THIEF]))


def test_entropy_is_maximal_on_uniform_and_falls_when_concentrated() -> None:
    uniform = BeliefMap(7)
    assert entropy(uniform) == pytest.approx(1.0)
    peaked = BeliefMap(7)
    scent = ScentField(7)
    scent.update((3, 3))
    peaked.observe_scent(scent, make_engine().board)
    assert entropy(peaked) < entropy(uniform)


def test_preview_entropy_rises_moving_and_falls_settling() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.STAY])
    after_one = entropy(mirror.belief)
    drive(mirror, engine, [Move.STAY] * 2)
    assert entropy(mirror.belief) < after_one  # settling concentrates the mirror
    estimator = LeakageEstimator(Role.THIEF, exposure_radius=1)
    me = engine.positions[Role.THIEF]
    settled = estimator.preview(mirror, engine, me)
    stepped = estimator.preview(mirror, engine, Move.E.applied_to(me))
    assert entropy(settled) < entropy(stepped)  # re-emitting in place sharpens


def test_staying_on_own_hotspot_is_most_exposing() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.STAY] * 3)
    estimator = LeakageEstimator(Role.THIEF, exposure_radius=1)
    stay = stealth_of(estimator, mirror, engine, Move.STAY)
    for move in (Move.N, Move.S, Move.E, Move.W):
        assert stay < stealth_of(estimator, mirror, engine, move)


def test_backtracking_into_own_trail_leaks_more_than_leaving_it() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.E] * 3)  # hot trail behind us along the row
    estimator = LeakageEstimator(Role.THIEF, exposure_radius=1)
    me = engine.positions[Role.THIEF]
    back = estimator.preview(mirror, engine, Move.W.applied_to(me))
    aside = estimator.preview(mirror, engine, Move.N.applied_to(me))
    assert mass_near(back, Move.W.applied_to(me), 1) > mass_near(
        aside, Move.N.applied_to(me), 1)
    assert stealth_of(estimator, mirror, engine, Move.W) < stealth_of(
        estimator, mirror, engine, Move.N)


def test_preview_never_mutates_mirror_or_scent() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.E, Move.STAY])
    belief_before = mirror.belief.values()
    scent_before = engine.scent[Role.THIEF].values()
    estimator = LeakageEstimator(Role.THIEF, exposure_radius=1)
    for move in Move:
        stealth_of(estimator, mirror, engine, move)
    assert mirror.belief.values() == belief_before
    assert engine.scent[Role.THIEF].values() == scent_before


def test_stealth_score_ignores_the_rival_position() -> None:
    """Own-side-only: engines differing ONLY in the cop's cell must yield
    byte-identical stealth scores for every candidate landing."""
    scores = []
    for cop_start in ((0, 0), (6, 6)):
        engine = GameEngine(7, cop_start, (3, 3), RULES)
        mirror = SelfMirror(Role.THIEF, 7)
        drive(mirror, engine, [Move.E, Move.N])
        estimator = LeakageEstimator(Role.THIEF, exposure_radius=1)
        scores.append([stealth_of(estimator, mirror, engine, m) for m in Move])
    assert scores[0] == scores[1]


def test_disabled_brain_decides_exactly_like_the_base_brain() -> None:
    engine, belief = make_engine(), BeliefMap(7)
    off = {**TUNING, "enabled": False}
    for turn in range(6):
        base = ThiefBrain(Role.THIEF, random.Random(turn))
        stealth = StealthThiefBrain(Role.THIEF, random.Random(turn), tuning=off)
        assert stealth.decide(engine, belief) == base.decide(engine, belief)
        engine.police_move(Move.STAY)
        engine.thief_move(Move[ThiefBrain(
            Role.THIEF, random.Random(turn)).decide(engine, belief)["move"]])
        belief.diffuse(engine.board)
        belief.observe_scent(engine.scent[Role.POLICE], engine.board)


def test_config_seam_loads_stealth_brain(config_dir) -> None:
    from p2p_thief.shared.config import Config

    config = Config.load(config_dir)
    config.private["strategy"] = {
        "thief_class": "p2p_thief.strategy.movement_deception:StealthThiefBrain"}
    brain = resolve_brain(config, Role.THIEF, random.Random(0))
    assert isinstance(brain, StealthThiefBrain)


def test_full_game_completes_with_movement_deception_on() -> None:
    """Integration: a whole blind arena game runs to a verdict, feature ON."""
    rng = random.Random(11)
    engine = make_engine()
    thief = StealthThiefBrain(Role.THIEF, rng, tuning=TUNING)
    cop = CopForArena(Role.POLICE, random.Random(12))
    cop_belief, thief_belief = BeliefMap(7), BeliefMap(7)
    from p2p_thief.domain import protocol

    while engine.outcome is Outcome.ONGOING:
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine, cop_belief))
        if engine.outcome is not Outcome.ONGOING:
            break
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, thief_belief))
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
        thief_belief.diffuse(engine.board)
        thief_belief.observe_scent(engine.scent[Role.POLICE], engine.board)
    assert engine.outcome in (Outcome.SURVIVAL, Outcome.CAPTURE)
    assert engine.turns_completed >= 1
