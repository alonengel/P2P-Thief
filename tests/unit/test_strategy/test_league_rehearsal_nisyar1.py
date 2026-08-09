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
    """nis-yar1's observed policy (g02+g06 sealed tapes): chase by BFS, and
    once close, SEAL — wall the thief's remaining exits one by one until the
    pocket closes (their [5,6] then [6,5] finisher); claim every landing.
    Placements honor the book: within one step of the cop's own cell."""
    me, thief = engine.positions[Role.POLICE], engine.positions[Role.THIEF]
    dist = bfs_distances(engine.board, thief)
    if barriers_left > 0 and dist.get(me, 99) <= 2:
        exits = [m.applied_to(thief) for m in (Move.N, Move.S, Move.E, Move.W)
                 if engine.board.is_passable(m.applied_to(thief))
                 and m.applied_to(thief) != me]
        legal = {me} | {m.applied_to(me) for m in (Move.N, Move.S, Move.E, Move.W)}
        sealable = [c for c in exits if c in legal]
        if sealable:  # fewest-remaining-exits first: close the pocket
            cell = min(sealable, key=lambda c: sum(
                1 for m in (Move.N, Move.S, Move.E, Move.W)
                if engine.board.is_passable(m.applied_to(c))))
            return {"type": "barrier", "cell": [cell[0], cell[1]]}, barriers_left - 1
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
        # senses in the LIVE perception's exact order: diffuse -> wall pin ->
        # claim pin -> scent -> hint tier (the misdirection lands AFTER the
        # pin and dilutes it — rehearsal fidelity finding, 2026-08-09)
        belief.diffuse(engine.board)
        if action["type"] == "barrier":
            belief.observe_barrier((action["cell"][0], action["cell"][1]), engine.board)
        if read_claims and action["type"] == "move":
            cop_cell = engine.positions[Role.POLICE]
            belief.observe_claimed_cell((cop_cell[0], cop_cell[1]))
        belief.observe_scent(engine.scent[Role.POLICE], engine.board)
        text = MISDIRECTION[turn % len(MISDIRECTION)]
        claim = parse_claim(text)
        if claim:
            belief.observe_hint(claim, engine.scent[Role.POLICE])
        else:
            region = landmark_region(text, 7)
            if region:
                belief.observe_region(region, engine.scent[Role.POLICE])
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


# Their g02 tape, verbatim from the sealed log: the diagonal staircase, then
# the seal — [5,6], then the [6,5] finisher on the cornered thief.
NISYAR1_G02_TAPE = [
    ("move", "S"), ("move", "E"), ("move", "S"), ("move", "S"), ("move", "E"),
    ("move", "E"), ("move", "S"), ("move", "E"), ("move", "S"), ("move", "E"),
    ("barrier", (5, 6)), ("move", "S"), ("stay", None), ("stay", None),
    ("barrier", (6, 5)),
]


def play_tape(seed: int) -> Outcome:
    """Their recorded cop, open-loop, vs our live belief pipeline."""
    import random as _random

    from p2p_thief.peer.perception import Perception
    from p2p_thief.shared.config import Config

    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief = ThiefBrain(Role.THIEF, _random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, Config.load("config"))
    # after the 15-turn tape their cop HOLDs (as recorded); play to the clock
    tape = NISYAR1_G02_TAPE + [("stay", None)] * 25
    for turn, (kind, arg) in enumerate(tape, start=1):
        if engine.outcome is not Outcome.ONGOING:
            break
        claim_cell = None
        if kind == "move":
            try:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": arg})
            except Exception:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": "STAY"})
            claim_cell = tuple(engine.positions[Role.POLICE])
        elif kind == "barrier":
            try:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "barrier", "cell": list(arg)})
            except Exception:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": "STAY"})
        else:
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, MISDIRECTION[turn % len(MISDIRECTION)],
                       barrier_cell=arg if kind == "barrier" else None,
                       claim_cell=claim_cell)
        protocol.apply_action(engine, Role.THIEF,
                              thief.decide(engine, percep.belief))
    return engine.outcome


def test_their_recorded_seal_tape_no_longer_kills_us() -> None:
    """The g02/g06 death, replayed from the sealed log: the staircase
    approach leaves the SE corner scoring 'optimal' for a conservative
    (distance, openness) thief until the two-wall seal lands. The fixed
    thief must leave the pocket before it closes."""
    survivals = sum(play_tape(seed) is Outcome.SURVIVAL for seed in range(5))
    assert survivals >= 4, f"tape survivals only {survivals}/5"
