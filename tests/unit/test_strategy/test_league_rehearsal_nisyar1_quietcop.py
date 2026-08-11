"""League rehearsal: nis-yar1's QUIET sealer cop (2026-08-11, g02/g04 tapes).

Their cop dropped the capture-claim channel entirely (claim=None every turn),
approaches behind landmark-lying prose, and seals with three walls once our
thief pockets itself. Both live games died in 13 turns to the IDENTICAL move
sequence. The kill exploits our blind-mode scorer: with no claims the
SHARP_BELIEF gate never opens, the conservative (distance, openness) score
maximizes distance from a stale peak, and the "safest" cell by that measure
is a corner — exactly the pocket a sealer needs. The fixed thief must deny
pockets even on mushy belief.
"""

import json
import random
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
SEEDS = range(5)
_TAPES = json.loads(
    (Path(__file__).parent / "nisyar1_cop_tapes.json").read_text(encoding="utf-8"))
_DELTA = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}


def play_tape(seed: int, game: str):
    """Their recorded quiet cop, open loop, vs our live thief pipeline."""
    tape = _TAPES[game]
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    thief = ThiefBrain(Role.THIEF, random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, Config.load("config"))
    for turn in range(RULES.max_moves):
        mv = tape["moves"][turn] if turn < len(tape["moves"]) else "MOVE:STAY"
        hint = tape["hints"][turn] if turn < len(tape["hints"]) else ""
        barrier_cell = None
        kind, _, arg = mv.partition(":")
        if kind == "BARRIER":
            me = engine.positions[Role.POLICE]
            delta = _DELTA[arg]
            cell = (me[0] + delta[0], me[1] + delta[1])
            try:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "barrier", "cell": [cell[0], cell[1]]})
                barrier_cell = cell
            except Exception:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": "STAY"})
        else:
            step = arg if arg in _DELTA else "STAY"
            try:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": step})
            except Exception:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        # live perception order; NO claim_cell — their cop went silent
        percep.observe(engine, Role.POLICE, hint,
                       barrier_cell=barrier_cell, claim_cell=None)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, percep.belief))
        if engine.outcome is not Outcome.ONGOING:
            break
    return engine.outcome, engine.turns_completed


def test_quiet_sealer_tapes_mostly_survived() -> None:
    """The claimless seal that killed us live in 13 turns, both recordings.

    Open-loop bar is 3/5, not 5/5, by design: a recorded cop cannot react,
    so some rng paths blunder into cells the GHOST happens to visit — cells
    a live chaser would have left because it would be following us instead.
    The live bar is the adaptive test below. Pre-pin these tapes were 0/5."""
    for game in ("g02", "g04"):
        survivals = sum(play_tape(seed, game)[0] is Outcome.SURVIVAL
                        for seed in SEEDS)
        assert survivals >= 3, f"{game} quiet sealer survived only {survivals}/5"


def _adaptive_cop_turn(engine, barriers_left):
    """Their behavior class, live: BFS-chase + exit-sealing, claim-silent."""
    from p2p_thief.domain.pathfind import bfs_distances
    from p2p_thief.domain.primitives import Move
    me, thief = engine.positions[Role.POLICE], engine.positions[Role.THIEF]
    dist = bfs_distances(engine.board, thief)
    if barriers_left > 0 and dist.get(me, 99) <= 2:
        exits = [m.applied_to(thief) for m in (Move.N, Move.S, Move.E, Move.W)
                 if engine.board.is_passable(m.applied_to(thief))
                 and m.applied_to(thief) != me]
        legal = {me} | {m.applied_to(me) for m in (Move.N, Move.S, Move.E, Move.W)}
        sealable = [c for c in exits if c in legal]
        if sealable:
            cell = min(sealable, key=lambda c: sum(
                1 for m in (Move.N, Move.S, Move.E, Move.W)
                if engine.board.is_passable(m.applied_to(c))))
            return {"type": "barrier", "cell": [cell[0], cell[1]]}, barriers_left - 1
    chase = min(engine.board.legal_moves(me),
                key=lambda m: dist.get(m.applied_to(me), 99))
    return {"type": "move", "move": chase.name}, barriers_left


def test_adaptive_quiet_sealer_is_beaten() -> None:
    """THE live bar: an ADAPTIVE chase-and-seal cop that never claims and
    lies in landmarks — the trail-head pin must keep the belief fresh enough
    to evade it. Pre-pin this exact regime captured us in 12-13 turns."""
    lies = _TAPES["g02"]["hints"]
    survivals = 0
    for seed in range(10):
        engine = GameEngine(7, (0, 0), (3, 3), RULES)
        thief = ThiefBrain(Role.THIEF, random.Random(seed))
        percep = Perception.for_peer(Role.THIEF, Config.load("config"))
        barriers_left, turn = 14, 0
        while engine.outcome is Outcome.ONGOING and turn < RULES.max_moves:
            turn += 1
            action, barriers_left = _adaptive_cop_turn(engine, barriers_left)
            barrier_cell = tuple(action["cell"]) if action["type"] == "barrier" else None
            try:
                protocol.apply_action(engine, Role.POLICE, action)
            except Exception:
                protocol.apply_action(engine, Role.POLICE,
                                      {"type": "move", "move": "STAY"})
            if engine.outcome is not Outcome.ONGOING:
                break
            percep.observe(engine, Role.POLICE, lies[turn % len(lies)],
                           barrier_cell=barrier_cell, claim_cell=None)
            protocol.apply_action(engine, Role.THIEF,
                                  thief.decide(engine, percep.belief))
        survivals += engine.outcome is Outcome.SURVIVAL
    assert survivals >= 9, f"adaptive quiet sealer: only {survivals}/10 survived"
