"""The corner seal that killed us three times identically (2026-08-11).

Book 3.4 (barrier law): a thief with no legal move is captured outright —
"גנב שנכלא ללא מהלך חוקי כלשהו … נחשב אף הוא ללכוד" — and the board edge
supplies half of that cage for free. nis-yar1's cop killed us at (6,6) by
walling (5,6) then (6,5); our thief had parked there because the blind
scorer ranked distance first and a corner keeps distance cheaply.
"""

import random

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def _exits(board, cell) -> int:
    return sum(1 for m in (Move.N, Move.S, Move.E, Move.W)
               if board.is_passable(m.applied_to(cell)))


def _belief_on(cell, grid=7) -> BeliefMap:
    belief = BeliefMap(grid)
    belief.observe_claimed_cell(cell)
    return belief


def test_thief_refuses_to_park_in_the_lethal_corner() -> None:
    """The live position: thief (6,6), cop (5,5), two walls left to spend.

    Distance alone says STAY (both exits step TOWARD the cop) — and staying
    is death in two cop turns. The thief must take an exit anyway."""
    for seed in range(8):
        engine = GameEngine(7, (5, 5), (6, 6), RULES)
        brain = ThiefBrain(Role.THIEF, random.Random(seed))
        action = brain.decide(engine, _belief_on((5, 5)))
        assert action["move"] != "STAY", f"seed {seed}: parked in the corner"
        landing = Move[action["move"]].applied_to((6, 6))
        assert _exits(engine.board, landing) > 2, (
            f"seed {seed}: fled {landing} with only "
            f"{_exits(engine.board, landing)} exits — still sealable")


def test_thief_leaves_an_edge_pocket_before_it_closes() -> None:
    """Same rule one step earlier: an edge cell with a wall already beside it
    is a pocket, and the clock is not a reason to sit in one."""
    engine = GameEngine(7, (4, 5), (6, 5), RULES)
    engine.board.add_barrier((6, 6))  # edge + one wall: two exits left
    for seed in range(8):
        brain = ThiefBrain(Role.THIEF, random.Random(seed))
        action = brain.decide(engine, _belief_on((4, 5)))
        landing = Move[action["move"]].applied_to((6, 5))
        assert _exits(engine.board, landing) >= _exits(engine.board, (6, 5)), (
            f"seed {seed}: moved into a tighter pocket ({landing})")
