"""Training-arena cop adversaries (thief-side, self-contained).

Two barrier-building sparring cops for evasion training - implemented HERE
because the mirrored-twin rule forbids cross-repo imports (duplicated static
code is legal; shared live state is not):

- TrapCop: compact heuristic - BFS pursuit + room-shrinking placements.
- DeepTrapCop: replays the twin repo's LEARNED Double-DQN cop. Its weights
  file (data/arena_cop_weights.json) is copied DATA produced by our own
  team's twin training run (0.74 capture vs a perfect evader); the cop-side
  feature code is duplicated below, byte-independent of the twin.
"""

import json
import random
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.errors import IllegalBarrierError
from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import validate_barrier_placement
from p2p_thief.strategy.rl_deep import Mlp

ARENA_WEIGHTS = Path(__file__).resolve().parents[3] / "data" / "arena_cop_weights.json"


class Hypothetical:
    """Board view with one extra barrier - peek at after-states."""

    def __init__(self, board, extra) -> None:
        self._board, self._extra, self.grid_size = board, extra, board.grid_size

    def is_passable(self, cell) -> bool:
        return cell != self._extra and self._board.is_passable(cell)


def barrier_candidates(engine: GameEngine) -> list:
    me = engine.positions[Role.POLICE]
    legal = []
    for cell in [me] + [m.applied_to(me) for m in (Move.N, Move.S, Move.E, Move.W)]:
        try:
            validate_barrier_placement(engine.board, engine.rules, me, cell)
            legal.append(cell)
        except IllegalBarrierError:
            continue
    return legal


def cop_actions(engine: GameEngine) -> list[dict]:
    me = engine.positions[Role.POLICE]
    actions = [protocol.move_action(m) for m in engine.board.legal_moves(me)]
    return actions + [protocol.barrier_action(c) for c in barrier_candidates(engine)]


def cop_features(engine: GameEngine, action: dict) -> list[float]:
    """The twin cop's 10 after-state features, duplicated verbatim in spirit."""
    me, thief = engine.positions[Role.POLICE], engine.positions[Role.THIEF]
    if action["type"] == "barrier":
        board, landing = Hypothetical(engine.board, tuple(action["cell"])), me
    else:
        board, landing = engine.board, Move[action["move"]].applied_to(me)
    from_thief = bfs_distances(board, thief)
    grid, horizon = engine.board.grid_size, 2.0 * engine.board.grid_size
    before = from_thief.get(me, UNREACHABLE)
    after = from_thief.get(landing, UNREACHABLE)
    d_after = 1.0 if after == UNREACHABLE else after / horizon
    d_before = 1.0 if before == UNREACHABLE else before / horizon
    escapes = sum(
        1 for m in (Move.N, Move.S, Move.E, Move.W) if board.is_passable(m.applied_to(thief))
    )
    wall = min(thief[0], thief[1], grid - 1 - thief[0], grid - 1 - thief[1])
    return [
        1.0, d_after, d_after - d_before, escapes / 4.0,
        len(from_thief) / float(grid * grid),
        1.0 if action["type"] == "barrier" else 0.0,
        (engine.rules.max_barriers - len(engine.board.barriers)) / engine.rules.max_barriers,
        1.0 if escapes <= 1 else 0.0,
        wall / (grid / 2.0),
        float((landing[0] + landing[1] + thief[0] + thief[1]) % 2),
    ]


class TrapCop:
    """Scripted barrier cop: BFS pursuit + room-shrinking placements."""

    def __init__(self, role: Role, rng: random.Random) -> None:
        self.role = role

    def decide(self, engine: GameEngine, belief=None) -> dict:
        me, thief = engine.positions[Role.POLICE], engine.positions[Role.THIEF]
        candidates = barrier_candidates(engine)
        if thief in candidates:
            return protocol.barrier_action(thief)  # rule 46: instant capture
        room = len(bfs_distances(engine.board, thief))
        d = bfs_distances(engine.board, thief).get(me, 99)
        if candidates and d <= 4:
            best = min(candidates,
                       key=lambda c: len(bfs_distances(Hypothetical(engine.board, c), thief)))
            if len(bfs_distances(Hypothetical(engine.board, best), thief)) < room:
                return protocol.barrier_action(best)
        from_thief = bfs_distances(engine.board, thief)
        move = min(engine.board.legal_moves(me),
                   key=lambda m: from_thief.get(m.applied_to(me), 99))
        return protocol.move_action(move)


class DeepTrapCop:
    """The twin's trained Double-DQN cop, replayed from copied weight DATA."""

    def __init__(self, role: Role, rng: random.Random) -> None:
        self.role, self.rng = role, rng
        self.net = Mlp(rng)
        self.net.load_state(
            json.loads(ARENA_WEIGHTS.read_text(encoding="utf-8"))["net"])

    def decide(self, engine: GameEngine, belief=None) -> dict:
        actions = self.rng.sample(cop_actions(engine), k=len(cop_actions(engine)))
        return max(actions, key=lambda a: self.net.forward(cop_features(engine, a))[0])
