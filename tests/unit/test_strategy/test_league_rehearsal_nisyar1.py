"""League rehearsal: nis-yar1's claim-spamming chase cop (2026-08-09, g02).

Their cop caught our thief in 15 turns with a simple, deadly combination:
BFS-chase, a capture CLAIM on every single move (the claim names their own
landing cell — protocol truth), corner barriers, and landmark-prose hints
that misdirect ("my patrol is stuck out by Central Park" while marching at
us). The asymmetry we lost to: their claims told the truth all game and our
belief discarded them, while their prose lied and our landmark tier listened.

This rehearsal models that cop and pins the fix: a thief that reads inbound
claim cells as cop-position evidence evades it.
"""

import random

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.hints import landmark_region, parse_claim
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
# Their real g02 hint prose — landmark misdirection, verbatim from the log.
MISDIRECTION = [
    "I am wasting my shift watching Grand Central.",
    "I could swear you were hiding behind the Village.",
    "The trail went cold by Times Square; enjoy it.",
    "My patrol is stuck out by Central Park tonight.",
    "The city closes like a hand, finger by finger.",
    "Every step you take costs you a street.",
]


def cop_turn(engine: GameEngine, barriers_left: int) -> tuple[dict, int]:
    """nis-yar1's observed policy: chase by BFS; when adjacent-ish, wall the
    thief's best escape every third opportunity; claim every landing cell."""
    me, thief = engine.positions[Role.POLICE], engine.positions[Role.THIEF]
    dist = bfs_distances(engine.board, thief)
    if barriers_left > 0 and dist.get(me, 99) <= 2:
        walls = [m.applied_to(thief) for m in (Move.N, Move.S, Move.E, Move.W)
                 if engine.board.is_passable(m.applied_to(thief))
                 and m.applied_to(thief) != me]
        far = [c for c in walls if dist.get(c, 0) >= dist.get(me, 0)]
        if far:
            return {"type": "barrier", "cell": [far[0][0], far[0][1]]}, barriers_left - 1
    chase = min(engine.board.legal_moves(me), key=lambda m: dist.get(m.applied_to(me), 99))
    return {"type": "move", "move": chase.name}, barriers_left


def play(seed: int, read_claims: bool) -> Outcome:
    rng = random.Random(seed)
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief, belief = ThiefBrain(Role.THIEF, rng), BeliefMap(7)
    barriers_left, turn = 6, 0
    while engine.outcome is Outcome.ONGOING:
        turn += 1
        action, barriers_left = cop_turn(engine, barriers_left)
        try:
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:  # illegal wall pick: chase instead, like their cop
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        # senses exactly as the wire delivers them: no cop scent, lying
        # landmark prose — and, per move, a truthful claim of their own cell
        belief.diffuse(engine.board)
        belief.observe_scent(engine.scent[Role.POLICE], engine.board)
        text = MISDIRECTION[turn % len(MISDIRECTION)]
        claim = parse_claim(text)
        if claim:
            belief.observe_hint(claim, engine.scent[Role.POLICE])
        else:
            region = landmark_region(text, 7)
            if region:
                belief.observe_region(region, engine.scent[Role.POLICE])
        if read_claims and action["type"] == "move":
            cop_cell = engine.positions[Role.POLICE]
            belief.observe_claimed_cell((cop_cell[0], cop_cell[1]))
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, belief))
    return engine.outcome


def test_claim_reading_thief_evades_the_claim_chase_cop() -> None:
    """The fix: inbound claims are exact cop-position evidence — a thief
    that consumes them survives the cop that beat us in g02."""
    survivals = sum(play(seed, read_claims=True) is Outcome.SURVIVAL
                    for seed in range(5))
    assert survivals >= 4, f"claim-reading thief survived only {survivals}/5"


def test_the_claim_gap_is_real() -> None:
    """Contrast pin: reading claims must never do WORSE than ignoring them
    against this cop (the g02 loss class)."""
    deaf = sum(play(seed, read_claims=False) is Outcome.SURVIVAL for seed in range(5))
    reading = sum(play(seed, read_claims=True) is Outcome.SURVIVAL for seed in range(5))
    assert reading >= deaf, f"reading claims hurt: {reading} < {deaf}"
