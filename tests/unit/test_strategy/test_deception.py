"""Deception seam: self-mirror exposure, lie budget/cooldown, pay-to-lie policy.

The mirror consumes ONLY our own emissions (own scent trail, own hint
claims); the policy sees the rival solely through the belief map — never a
true rival position. The counter-deception check proves the receiving side's
profiler still down-weights a profiled liar under the new policy.
"""

import random
from pathlib import Path
from types import SimpleNamespace

from p2p_thief.domain.belief import BeliefMap, claimed_region
from p2p_thief.domain.board import Board
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.domain.scent import ScentField
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.deception import (
    Deceiver,
    DeceptionClock,
    DeceptionPolicy,
    SelfMirror,
    decoy_claim,
)
from p2p_thief.strategy.hints import TEMPLATES, build_hint
from p2p_thief.strategy.profiler import OpponentProfiler

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def make_engine() -> GameEngine:
    return GameEngine(7, (0, 0), (3, 3), RULES)


def drive(mirror: SelfMirror, engine: GameEngine, moves, claims=None) -> None:
    """Full turns (cop stays, we move); the mirror observes our side at the
    same point the rival does — post-boundary, since the thief closes turns."""
    for index, move in enumerate(moves):
        engine.police_move(Move.STAY)
        engine.thief_move(move)
        mirror.observe_own_turn(engine, claims[index] if claims else None)


def my_exposure(mirror: SelfMirror, engine: GameEngine) -> float:
    return mirror.exposure(engine.positions[Role.THIEF], radius=1)


def aimed_belief(cell) -> BeliefMap:
    """A belief map whose argmax is `cell` (stand-in for the rival estimate)."""
    belief = BeliefMap(7)
    scent = ScentField(7)
    scent.update(cell)
    belief.observe_scent(scent, Board(7))
    return belief


def tuning(**overrides) -> dict:
    base = {"max_lies": 3, "cooldown_turns": 4, "exposure_threshold": 0.35,
            "opponent_distance_threshold": 3, "exposure_radius": 1}
    return base | overrides


def test_mirror_argmax_tracks_own_cell() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.STAY, Move.STAY])
    assert mirror.belief.argmax_cell() == engine.positions[Role.THIEF]


def test_exposure_rises_standing_still() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    start = my_exposure(mirror, engine)
    drive(mirror, engine, [Move.STAY])
    after_one = my_exposure(mirror, engine)
    drive(mirror, engine, [Move.STAY])
    assert start < after_one < my_exposure(mirror, engine)


def test_exposure_falls_after_moving_away() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.STAY] * 3)
    settled = my_exposure(mirror, engine)
    drive(mirror, engine, [Move.E] * 3)
    assert my_exposure(mirror, engine) < settled / 2


def test_decoy_lie_cuts_exposure_versus_truthful_claim() -> None:
    honest, liar = SelfMirror(Role.THIEF, 7), SelfMirror(Role.THIEF, 7)
    honest_engine, liar_engine = make_engine(), make_engine()
    drive(honest, honest_engine, [Move.STAY] * 3 + [Move.E], ["STAY"] * 3 + ["E"])
    drive(liar, liar_engine, [Move.STAY] * 3 + [Move.E], ["STAY"] * 3 + ["W"])
    assert my_exposure(liar, liar_engine) < my_exposure(honest, honest_engine)


def test_clock_enforces_budget() -> None:
    clock = DeceptionClock(max_lies=2, cooldown_turns=0)
    assert clock.may_lie(1)
    clock.record_lie(1)
    assert clock.may_lie(2)
    clock.record_lie(2)
    assert not clock.may_lie(30)


def test_clock_enforces_cooldown() -> None:
    clock = DeceptionClock(max_lies=9, cooldown_turns=3)
    clock.record_lie(4)
    assert not clock.may_lie(5) and not clock.may_lie(7)
    assert clock.may_lie(8)


def test_decoy_points_away_from_true_heading() -> None:
    rng = random.Random(0)
    assert decoy_claim(Move.N, rng) == "S"
    assert decoy_claim(Move.S, rng) == "N"
    assert decoy_claim(Move.E, rng) == "W"
    assert decoy_claim(Move.W, rng) == "E"
    assert decoy_claim(Move.STAY, rng) in {"N", "S", "E", "W"}


def test_build_hint_uses_decoy_only_when_lying() -> None:
    text, claim, truth = build_hint(Move.N, False, 15, random.Random(0), decoy="S")
    assert (claim, truth) == ("S", False) and text in TEMPLATES["S"]
    _, claim, truth = build_hint(Move.N, True, 15, random.Random(0), decoy="S")
    assert (claim, truth) == ("N", True)


def test_policy_lies_only_under_the_full_conjunction() -> None:
    engine, mirror = make_engine(), SelfMirror(Role.THIEF, 7)
    drive(mirror, engine, [Move.STAY] * 3)          # exposure ~0.51 >= 0.35
    near = SimpleNamespace(belief=aimed_belief((3, 4)))   # distance 1 <= 3
    far = SimpleNamespace(belief=aimed_belief((0, 0)))    # distance 6 > 3
    clock = DeceptionClock(max_lies=3, cooldown_turns=4)
    policy = DeceptionPolicy(tuning())
    assert policy.decide_truth(engine, far, mirror, clock, 4)        # rival far
    fresh = SelfMirror(Role.THIEF, 7)                                # uniform ~0.10
    assert policy.decide_truth(engine, near, fresh, clock, 4)        # not exposed
    spent = DeceptionClock(max_lies=0, cooldown_turns=0)
    assert policy.decide_truth(engine, near, mirror, spent, 4)       # no budget
    assert not policy.decide_truth(engine, near, mirror, clock, 4)   # all legs met


def test_deceiver_burns_budget_and_logs_decisions(config_dir: Path) -> None:
    config = Config.load(config_dir)
    config.private["deception"] = {"max_lies": 1, "cooldown_turns": 2,
                                   "exposure_threshold": 0.0,
                                   "opponent_distance_threshold": 99}
    deceiver = Deceiver(Role.THIEF, config, random.Random(3))
    perception = SimpleNamespace(belief=aimed_belief((3, 4)))
    engine = make_engine()
    assert deceiver.plan_hint(engine, perception, Move.E, 1) == ("W", False)
    assert deceiver.plan_hint(engine, perception, Move.E, 2) == ("E", True)
    assert deceiver.decisions == [False, True]


def test_deception_config_defaults_and_overrides(config_dir: Path) -> None:
    config = Config.load(config_dir)
    assert config.deception() == {
        "max_lies": 3, "cooldown_turns": 4, "exposure_threshold": 0.35,
        "opponent_distance_threshold": 3, "exposure_radius": 1,
        "baseline_truth_probability": 0.5,
    }
    config.private["deception"] = {"max_lies": 7, "exposure_threshold": 0.6}
    tuned = config.deception()
    assert tuned["max_lies"] == 7 and tuned["exposure_threshold"] == 0.6
    assert tuned["cooldown_turns"] == 4     # untouched keys keep their defaults


def observed_after_hint(opponent: str, profiler: OpponentProfiler) -> float:
    """Mass the receiver's belief leaves in the claimed region after a hint
    from `opponent` — same scent evidence, only the reputation differs."""
    engine = make_engine()
    engine.police_move(Move.STAY)
    engine.thief_move(Move.N)               # fresh trail inside the claimed north
    perception = Perception(Role.POLICE, 7)
    perception.profiler, perception.opponent_id = profiler, opponent
    perception.observe(engine, Role.THIEF, "North wind suits me fine today.")
    region = claimed_region("N", 7)
    return sum(perception.belief.value_at(cell) for cell in region)


def test_profiled_liar_hints_get_down_weighted(tmp_path: Path) -> None:
    profiler = OpponentProfiler(tmp_path / "profiles.json")
    profiler.record_audited_verdicts("liar", [False] * 10)
    assert observed_after_hint("liar", profiler) < observed_after_hint("neutral", profiler)
