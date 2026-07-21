"""Certificate soundness against the physics itself: from a certified state,
follow the certified move and let the cop try EVERY legal reply (moves and
barriers) - each line must stay certified and end in SURVIVAL, never capture.
Plus: a full blind game with the wrapper completes legally."""

import random

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.errors import IllegalBarrierError
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet, validate_barrier_placement
from p2p_thief.strategy.arena_cop import TrapCop
from p2p_thief.strategy.endgame import DEFAULTS, CertifiedThiefBrain, SurvivalCertificate

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
TURNS_LEFT = 3


class FakeBelief:
    """Support-only belief stub (twin of the one in test_endgame.py)."""

    def __init__(self, grid_size: int, cells: list) -> None:
        self.grid_size, self._cells = grid_size, list(cells)

    def values(self) -> list[list[float]]:
        grid = [[0.0] * self.grid_size for _ in range(self.grid_size)]
        for row, col in self._cells:
            grid[row][col] = 1.0 / len(self._cells)
        return grid

    def argmax_cell(self):
        return self._cells[0]


def make_engine() -> GameEngine:
    """Cop two steps off at (0,4), thief at (0,2), 3 turns to survive."""
    engine = GameEngine(7, (0, 4), (0, 2), RULES)
    engine.turns_completed = RULES.survival_threshold - TURNS_LEFT
    engine.police_move(Move.STAY)  # hand the half-turn to the thief
    return engine


def cop_replies(engine: GameEngine) -> list[dict]:
    cop = engine.positions[Role.POLICE]
    actions = [protocol.move_action(m) for m in engine.board.legal_moves(cop)]
    for wall in (cop, *(m.applied_to(cop) for m in (Move.N, Move.S, Move.E, Move.W))):
        try:
            validate_barrier_placement(engine.board, engine.rules, cop, wall)
            actions.append(protocol.barrier_action(wall))
        except IllegalBarrierError:
            continue
    return actions


def explore(script: tuple = ()) -> None:
    engine, step = make_engine(), 0
    certificate = SurvivalCertificate({**DEFAULTS, "enabled": True})
    while engine.outcome is Outcome.ONGOING:
        oracle = FakeBelief(7, [engine.positions[Role.POLICE]])  # test-side truth
        locked = certificate.lock(engine, oracle)
        assert locked is not None, f"certificate lost its own line: {script}"
        protocol.apply_action(engine, Role.THIEF, locked)
        assert engine.outcome is not Outcome.CAPTURE, f"certified into capture: {script}"
        if engine.outcome is not Outcome.ONGOING:
            break
        if step < len(script):
            protocol.apply_action(engine, Role.POLICE, script[step])
            assert engine.outcome is not Outcome.CAPTURE, f"cop refuted: {script}"
        else:
            for reply in cop_replies(engine):
                explore((*script, reply))
            return
        step += 1
    assert engine.outcome is Outcome.SURVIVAL


def test_certified_line_survives_every_cop_reply() -> None:
    explore()


def test_full_blind_game_with_certificate_wrapper_completes() -> None:
    for seed in range(3):
        engine = GameEngine(7, (0, 0), (3, 3), RULES)
        cop = TrapCop(Role.POLICE, random.Random(seed))
        thief = CertifiedThiefBrain(Role.THIEF, random.Random(seed + 500),
                                    {"strategy": {"endgame": {"enabled": True}}})
        belief = BeliefMap(7)
        while engine.outcome is Outcome.ONGOING:
            protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
            if engine.outcome is not Outcome.ONGOING:
                break
            belief.diffuse(engine.board)
            belief.observe_scent(engine.scent[Role.POLICE], engine.board)
            protocol.apply_action(engine, Role.THIEF, thief.decide(engine, belief))
        assert engine.outcome in (Outcome.CAPTURE, Outcome.SURVIVAL)
