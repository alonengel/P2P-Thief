"""Kill-juncture regressions: each is a line that actually ended a game —
two reconstructed from our own replayed losses, one from a herded corner.
They are the doctrine's reason to exist, so they live apart from the
unit-level knob tests in test_doctrine.py and must never be relaxed."""

import random

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.doctrine import DEFAULTS, DoctrineThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
STEALTH = {"enabled": True, "blend_weight": 8.0, "safe_distance": 3, "exposure_radius": 1}
ON = {**DEFAULTS, "fresh_flee": True, "stay_cap": True, "pocket_escape": True,
      "forecast": True, "lethal_gate": True}


def observe(belief: BeliefMap, engine: GameEngine, barrier=None) -> None:
    """The thief's real perception order: diffuse, barrier origin, scent."""
    belief.diffuse(engine.board)
    if barrier is not None:
        belief.observe_barrier(barrier, engine.board)
    belief.observe_scent(engine.scent[Role.POLICE], engine.board)


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


def test_lethal_gate_refuses_the_herded_corner_walk_in() -> None:
    """Third kill juncture — the herded-corner walk-in. Sealed into (6,6)
    with a hunter one step north, the posterior is MISLED north-west, so the
    widened flee term ranks the hunter's OWN cell as the farthest landing and
    walks straight into it. Landings a believed hunter can end next turn
    (occupy or wall) must rank below every landing it cannot, however far."""
    engine = GameEngine(7, (5, 6), (6, 6), RULES)
    engine.police_place_barrier((5, 5))  # seals the corner's west exit
    engine.thief_move(Move.STAY)
    engine.police_place_barrier((4, 6))  # ...and the north approach
    engine.thief_move(Move.STAY)
    belief = BeliefMap(7)  # posterior misled north-west; the truth is a minor peak
    belief._p = [[0.001] * 7 for _ in range(7)]
    belief._p[4][5], belief._p[3][6], belief._p[5][6] = 0.55, 0.20, 0.15
    belief._normalize()
    assert belief.argmax_cell() == (4, 5)  # the misleading peak the flee term chases
    brain = DoctrineThiefBrain(Role.THIEF, random.Random(17), tuning=STEALTH,
                               doctrine=dict(ON))
    landing = Move[brain.decide(engine, belief)["move"]].applied_to((6, 6))
    assert landing != (5, 6)  # never onto a believed hunter, whatever the distance
    assert landing == (6, 5)  # the one landing no support cell can end


def test_lethal_gate_is_inert_when_every_landing_is_covered() -> None:
    """No silent freeze: when every candidate is end-able the gate ties and
    the doctrine ordering below it decides exactly as before."""
    engine = GameEngine(7, (5, 6), (6, 6), RULES)
    engine.police_place_barrier((5, 5))
    engine.thief_move(Move.STAY)
    belief = BeliefMap(7)
    belief._p = [[0.001] * 7 for _ in range(7)]
    belief._p[6][5], belief._p[5][6], belief._p[6][6] = 0.4, 0.35, 0.25
    belief._normalize()
    gated = DoctrineThiefBrain(Role.THIEF, random.Random(19), tuning=STEALTH,
                               doctrine=dict(ON))
    plain = DoctrineThiefBrain(Role.THIEF, random.Random(19), tuning=STEALTH,
                               doctrine={**ON, "lethal_gate": False})
    assert gated.decide(engine, belief) == plain.decide(engine, belief)


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
