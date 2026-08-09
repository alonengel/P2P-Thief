"""Shipped evasion brain: distance + a one-ply adversarial TRAP FORECAST.

Policy: run out the survival clock without walking into a wall-able pocket.
The cop may place a barrier only within one step of ITS OWN cell (book p. 37)
— so for every candidate landing we compute the WORST-case reachable region
after the cop's best legal placement next turn, clock-capped (a region that
outlives the remaining turns is safe regardless of size). Distance still
rules at knife range; trap-safety rules everywhere else.
"""


from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Cell, Move, Role
from p2p_thief.strategy.brain_base import BrainBase

# Belief peak mass at which the estimate is trusted like exact information.
# The wall FORECAST was measured catastrophic on STALE belief (lag-1 cop:
# survival 100 -> 0), so it stayed exact-only — but a claim-per-move rival
# pins our belief to its true cell every turn (league 2026-08-09), and a
# pinned peak is not stale (live trace: 0.83-0.89 mass). A merely-moderate
# peak (e.g. a misled 0.55) must NOT open the gate — that is the stale-info
# hazard the doctrine tests pin. Below the gate the conservative scorer
# stands.
SHARP_BELIEF = 0.75


class _Blocked:
    """Board view with one hypothetical barrier (trap-forecast probes)."""

    def __init__(self, board, extra: Cell) -> None:
        self._board, self._extra, self.grid_size = board, extra, board.grid_size

    def is_passable(self, cell) -> bool:
        return cell != self._extra and self._board.is_passable(cell)


class ThiefBrain(BrainBase):
    """Distance-maximizing, trap-forecasting, corner-averse evasion."""

    def decide(self, engine: GameEngine, belief=None) -> dict:
        # Blind mode (real games): flee the belief peak, never the true cell.
        # The adversarial wall FORECAST runs only on exact information: fed a
        # stale/believed cop cell it dodges phantom walls and walks into real
        # ones (measured: TrapCop lag-1 survival 100 -> 0). Belief play stays
        # conservative distance+openness, which stale info cannot poison.
        exact = belief is None
        cop = engine.positions[Role.POLICE] if exact else belief.argmax_cell()
        # A claim-pinned peak is trusted like exact info: the forecast that
        # dodges wall traps needs a true cop cell, and a claim provides one.
        # Minimal belief fakes (endgame certificates) carry no value_at —
        # they read as diffuse and keep the conservative scorer.
        peak = getattr(belief, "value_at", lambda _cell: 0.0)
        trust = exact or peak(cop) >= SHARP_BELIEF
        me = engine.positions[Role.THIEF]
        distances = bfs_distances(engine.board, cop)

        best_move = Move.STAY
        best_score = self._score(engine, me, distances, cop, trust)
        for move in self.rng.sample(list(Move), k=len(Move)):
            target = move.applied_to(me)
            if move is Move.STAY or not engine.board.is_passable(target):
                continue
            score = self._score(engine, target, distances, cop, trust)
            if score > best_score:
                best_move, best_score = move, score
        return protocol.move_action(best_move)

    def _after_best_wall(self, engine: GameEngine, cell: Cell, cop: Cell) -> tuple:
        """(escapes, region) from `cell` after the cop's BEST reply wall.

        Placements are limited to the cop's cell + its four orthogonal
        neighbors (book p. 37); a wall on `cell` itself is instant capture.
        """
        escapes = sum(1 for m in (Move.N, Move.S, Move.E, Move.W)
                      if engine.board.is_passable(m.applied_to(cell)))
        region = len(bfs_distances(engine.board, cell))
        if len(engine.board.barriers) >= engine.rules.max_barriers:
            return escapes, region
        for delta in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            wall = (cop[0] + delta[0], cop[1] + delta[1])
            if wall == cell:
                return 0, 0  # the cop can simply wall our landing: captured
            if engine.board.is_passable(wall):
                blocked = _Blocked(engine.board, wall)
                escapes = min(escapes, sum(
                    1 for m in (Move.N, Move.S, Move.E, Move.W)
                    if blocked.is_passable(m.applied_to(cell))))
                region = min(region, len(bfs_distances(blocked, cell)))
        return escapes, region

    def _score(self, engine: GameEngine, cell: Cell, distances: dict[Cell, int],
               cop: Cell, exact: bool) -> tuple:
        """Exact-info order: don't be adjacent > survive the cop's best wall
        (escapes, then region) > stay off the walls (trap cops harvest
        wall-huggers) > raw distance > openness — the forecast outranks
        distance beyond knife range because room, not distance, is life.
        Belief order: classic (distance, openness) — stale-info-proof.
        """
        distance = distances.get(cell, UNREACHABLE)
        if distance == UNREACHABLE:
            distance = 10**6  # unreachable by the cop = maximal safety
        openness = sum(
            1
            for m in (Move.N, Move.S, Move.E, Move.W)
            if engine.board.is_passable(m.applied_to(cell))
        )
        if not exact:
            return (distance, openness)
        escapes, region = self._after_best_wall(engine, cell, cop)
        grid = engine.board.grid_size
        wall_distance = min(cell[0], cell[1], grid - 1 - cell[0], grid - 1 - cell[1])
        return (min(distance, 2), escapes, region, wall_distance, distance, openness)


class CopForArena(BrainBase):
    """Pursuit sparring partner for OUR self-play arena only (the real police
    brain lives in the P2P-Police repo): minimize BFS distance to the thief."""

    def decide(self, engine: GameEngine, belief=None) -> dict:
        thief = belief.argmax_cell() if belief is not None else engine.positions[Role.THIEF]
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
