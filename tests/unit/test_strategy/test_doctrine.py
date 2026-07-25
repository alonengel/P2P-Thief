"""Anti-freeze doctrine tests: belief-play camping is the death mode our own
replayed losses exposed — the capped flee term ties, stealth tie-breaks
settle on STAY, the camp saturates our own trail into a beacon, and a
patient hunter walls the pocket. Each counter-measure is config-gated and
must collapse to the plain stealth brain when disabled."""

import random
from types import SimpleNamespace

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.domain.scent import ScentField
from p2p_thief.strategy.doctrine import (
    DEFAULTS,
    DoctrineThiefBrain,
    doctrine_settings,
    fresh_evidence,
)
from p2p_thief.strategy.movement_deception import StealthThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
STEALTH = {"enabled": True, "blend_weight": 8.0, "safe_distance": 3, "exposure_radius": 1}
OFF = {**DEFAULTS, "fresh_flee": False, "stay_cap": False, "pocket_escape": False, "forecast": False}
ON = {**DEFAULTS, "fresh_flee": True, "stay_cap": True, "pocket_escape": True, "forecast": True}


def observe(belief: BeliefMap, engine: GameEngine, barrier=None) -> None:
    """The thief's real perception order: diffuse, barrier origin, scent."""
    belief.diffuse(engine.board)
    if barrier is not None:
        belief.observe_barrier(barrier, engine.board)
    belief.observe_scent(engine.scent[Role.POLICE], engine.board)


def test_doctrine_settings_defaults_and_overrides() -> None:
    settings = doctrine_settings({})
    assert settings == DEFAULTS
    tuned = doctrine_settings({"strategy": {"doctrine": {"max_consecutive_stays": 5}}})
    assert tuned["max_consecutive_stays"] == 5
    assert tuned["barrier_alert_radius"] == DEFAULTS["barrier_alert_radius"]


def test_fresh_evidence_detects_live_trails_near_us_only() -> None:
    assert not fresh_evidence(ScentField(7), 1, (3, 3), 4)  # silence
    live = ScentField(7)
    live.update((3, 3))
    # A fresh center right next to us arms flight; the SAME field read from
    # far away does not — the rival's own vicinity always burns fresh.
    assert fresh_evidence(live, 1, (3, 4), 4) and not fresh_evidence(live, 1, (0, 6), 1)
    aged = SimpleNamespace(values=lambda: [[0.53 if (r, c) == (1, 0) else 0.0
                                            for c in range(7)] for r in range(7)])
    assert not fresh_evidence(aged, 1, (1, 1), 4)  # stale reading: reach >= 2


def test_disabled_doctrine_decides_exactly_like_the_stealth_brain() -> None:
    # Keep-gate identity: every knob OFF must reproduce the shipped brain.
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    belief = BeliefMap(7)
    for turn in range(6):
        stealth = StealthThiefBrain(Role.THIEF, random.Random(turn), tuning=STEALTH)
        doctrine = DoctrineThiefBrain(Role.THIEF, random.Random(turn),
                                      tuning=STEALTH, doctrine=OFF)
        assert doctrine.decide(engine, belief) == stealth.decide(engine, belief)
        engine.police_move(Move.STAY)
        engine.thief_move(Move[StealthThiefBrain(
            Role.THIEF, random.Random(turn), tuning=STEALTH,
        ).decide(engine, belief)["move"]])
        observe(belief, engine)


def test_stay_cap_bans_camping_once_exposed() -> None:
    # After max_consecutive_stays with the self-mirror glowing, STAY is
    # struck from the candidate set — the brain must move, and a move
    # resets the consecutive-stay run.
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(2), tuning=STEALTH, doctrine={**OFF, "stay_cap": True})
    belief = BeliefMap(7)  # uniform: the flee term ties everywhere
    for _ in range(4):
        engine.police_move(Move.STAY)
        engine.thief_move(Move.STAY)  # the camp saturates our own beacon
        observe(belief, engine)
    brain._stays = brain.doctrine["max_consecutive_stays"]  # camped that long
    action = brain.decide(engine, belief)
    assert action["move"] != "STAY"
    assert brain._stays == 0  # the move reset the run


def test_fresh_evidence_lifts_the_flee_cap() -> None:
    # With a live rival trail burning near us the flee term ranks REAL
    # distance again: the uncapped brain must take a landing 4+ steps from
    # the believed hunter, beyond the safe_distance cap of 3.
    engine = GameEngine(7, (5, 1), (2, 1), RULES)
    belief = BeliefMap(7)
    for _ in range(2):
        engine.police_move(Move.STAY)
        engine.thief_move(Move.STAY)
        observe(belief, engine)  # hunter's fresh trail three cells south
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(5), tuning=STEALTH,
                               doctrine={**OFF, "fresh_flee": True})
    landing = Move[brain.decide(engine, belief)["move"]].applied_to((2, 1))
    distances = bfs_distances(engine.board, belief.argmax_cell())
    assert distances.get(landing, 0) >= 4  # beyond the cap: real flight


def test_new_wall_near_us_arms_cross_quadrant_escape() -> None:
    engine = GameEngine(7, (2, 3), (1, 5), RULES)
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(7), tuning=STEALTH,
                               doctrine={**OFF, "pocket_escape": True})
    belief = BeliefMap(7)
    observe(belief, engine)
    brain.decide(engine, belief)  # baseline: no walls known yet
    engine.police_place_barrier((2, 4))  # lands 2 cells from us
    engine.thief_move(Move.STAY)
    observe(belief, engine, barrier=(2, 4))
    brain.decide(engine, belief)
    assert brain._escape_until > engine.turns_completed  # flight armed
    assert brain._escape_dist  # cross-quadrant target resolved


def test_far_wall_does_not_arm_escape() -> None:
    engine = GameEngine(7, (5, 5), (1, 1), RULES)
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(8), tuning=STEALTH,
                               doctrine={**OFF, "pocket_escape": True})
    belief = BeliefMap(7)
    observe(belief, engine)
    brain.decide(engine, belief)
    engine.police_place_barrier((5, 6))  # eight cells away: not our pocket
    engine.thief_move(Move.STAY)
    observe(belief, engine, barrier=(5, 6))
    brain.decide(engine, belief)
    assert brain._escape_until <= engine.turns_completed


def test_juncture_camped_thief_moves_out_when_the_hunter_closes() -> None:
    """Reconstructed kill pattern from our own replayed logs: a thief camped
    nine rounds at (5,1) — its own beacon saturated — while the hunter
    closed (3,2)->(4,2)->(5,2) on a live trail. The capped-flee line saw
    every landing tie at the cap and settled on STAY until the pocket shut.
    The doctrine brain must move out, never inward."""
    engine = GameEngine(7, (3, 2), (5, 1), RULES)
    belief = BeliefMap(7)
    for move in [Move.STAY] * 7 + [Move.S, Move.S]:  # nine camped rounds
        engine.police_move(move)
        engine.thief_move(Move.STAY)
        observe(belief, engine)
    assert engine.positions[Role.POLICE] == (5, 2)  # knife range, live trail
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(11), tuning=STEALTH,
                               doctrine=dict(ON))
    action = brain.decide(engine, belief)
    assert action["move"] != "STAY"
    landing = Move[action["move"]].applied_to((5, 1))
    distances = bfs_distances(engine.board, belief.argmax_cell())
    assert distances.get(landing, 0) >= distances.get((5, 1), 0)  # not inward


def test_juncture_pocket_walls_trigger_flight_not_a_deeper_camp() -> None:
    """Second reconstructed kill: camped at (1,5) while walls landed at
    (2,4) then (1,3) — a 2-cell-radius seal in progress. The old line kept
    the corner and died walled in; the doctrine brain must leave the pocket
    (never STAY, never deeper into the corner)."""
    engine = GameEngine(7, (2, 3), (1, 5), RULES)
    belief = BeliefMap(7)
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(13), tuning=STEALTH,
                               doctrine=dict(ON))
    observe(belief, engine)
    brain.decide(engine, belief)  # baseline before any wall exists
    engine.police_place_barrier((2, 4))
    engine.thief_move(Move.STAY)
    observe(belief, engine, barrier=(2, 4))
    engine.police_move(Move.N)  # hunter slides to (1, 3)
    engine.thief_move(Move.STAY)
    observe(belief, engine)
    engine.police_place_barrier((1, 3))  # under his own feet: seal forming
    engine.thief_move(Move.STAY)
    observe(belief, engine, barrier=(1, 3))
    action = brain.decide(engine, belief)
    assert action["move"] != "STAY"
    landing = Move[action["move"]].applied_to((1, 5))
    assert landing not in {(0, 5), (0, 6), (1, 6)}  # not deeper into the seal
