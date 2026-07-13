"""Shipped evasion brain (stage 3: full information; belief arrives stage 4).

Policy: run out the survival clock. Each turn, pick the legal move maximizing
the TRUE (barrier-aware BFS) distance from the cop, tie-breaking toward open
ground (more escape routes) so the thief never trades distance for a corner —
a cornered thief is a captured thief (rule 47).
"""


from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Cell, Move, Role
from p2p_thief.strategy.brain_base import BrainBase


class ThiefBrain(BrainBase):
    """Distance-maximizing, corner-averse evasion."""

    def decide(self, engine: GameEngine) -> dict:
        cop = engine.positions[Role.POLICE]
        me = engine.positions[Role.THIEF]
        distances = bfs_distances(engine.board, cop)

        best_move = Move.STAY
        best_score = self._score(engine, me, distances)
        for move in self.rng.sample(list(Move), k=len(Move)):
            target = move.applied_to(me)
            if move is Move.STAY or not engine.board.is_passable(target):
                continue
            score = self._score(engine, target, distances)
            if score > best_score:
                best_move, best_score = move, score
        return protocol.move_action(best_move)

    def _score(self, engine: GameEngine, cell: Cell, distances: dict[Cell, int]) -> tuple:
        """(distance from cop, openness): cut-off cells are paradise (the cop
        cannot reach them at all); otherwise farther is better, and among
        equals prefer cells with more open orthogonal neighbors."""
        distance = distances.get(cell, UNREACHABLE)
        if distance == UNREACHABLE:
            distance = 10**6  # unreachable by the cop = maximal safety
        openness = sum(
            1
            for m in (Move.N, Move.S, Move.E, Move.W)
            if engine.board.is_passable(m.applied_to(cell))
        )
        return (distance, openness)


class CopForArena(BrainBase):
    """Pursuit sparring partner for OUR self-play arena only (the real police
    brain lives in the P2P-Police repo): minimize BFS distance to the thief."""

    def decide(self, engine: GameEngine) -> dict:
        thief = engine.positions[Role.THIEF]
        me = engine.positions[Role.POLICE]
        distances = bfs_distances(engine.board, thief)
        best_move, best = Move.STAY, distances.get(me, UNREACHABLE)
        for move in self.rng.sample(list(Move), k=len(Move)):
            target = move.applied_to(me)
            if move is Move.STAY or not engine.board.is_passable(target):
                continue
            distance = distances.get(target, UNREACHABLE)
            if distance != UNREACHABLE and (best == UNREACHABLE or distance < best):
                best_move, best = move, distance
        return protocol.move_action(best_move)
