"""Probe thief for FRIENDLY sparring — a decoy that runs experiments.

A friendly is the only place we see their cop react to POSITIONS WE CHOOSE.
This brain walks a configured waypoint tour (each leg is a question: what
does their cop do when we sit in the NE? when we hug the south edge?) while
looking like a plausible wandering thief. The answers are read afterwards
from the tapes: their revealed moves and walls, indexed against our known
script. It doubles as a decoy — the room-first brain stays unseen.

Selection and script are config-only (FRIENDLY overlay):
    [strategy]
    thief_class = "p2p_thief.strategy.probe:ProbeThiefBrain"
    [strategy.probe]
    waypoints = [[1, 5], [5, 5], [1, 1], [5, 1]]   # the tour, in order
    dwell_turns = 3                                # sit this long per stop
Movement is belief-blind BFS toward the current waypoint; the only reactive
piece is a survival dodge (step away when the believed cop closes to gap 1,
never into a cell with fewer than 2 exits) so probe games still finish and
still collect the late-game data. Sealed records stay honest throughout.
"""

from p2p_thief.domain import protocol
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.strategy.brain_base import BrainBase

PROBE_DEFAULTS: dict = {"waypoints": [[1, 5], [5, 5], [1, 1], [5, 1]],
                        "dwell_turns": 3}


class ProbeThiefBrain(BrainBase):
    """Waypoint tour + dwell + adjacency dodge; belief-only, truth-blind."""

    def __init__(self, role, rng, config=None) -> None:
        super().__init__(role, rng)
        table = {**PROBE_DEFAULTS,
                 **(config.private.get("strategy", {}).get("probe", {})
                    if config is not None else {})}
        self.stops = [tuple(cell) for cell in table["waypoints"]]
        self.dwell_turns = int(table["dwell_turns"])
        self._leg, self._dwelt = 0, 0

    def decide(self, engine, belief=None) -> dict:
        me = engine.positions[Role.THIEF]
        cop = belief.argmax_cell() if belief is not None else None
        moves = [m for m in (Move.N, Move.S, Move.E, Move.W)
                 if engine.board.is_passable(m.applied_to(me))]
        # Survival dodge outranks the tour: the probe must reach its answers.
        if cop is not None and abs(me[0] - cop[0]) + abs(me[1] - cop[1]) <= 1:
            away = bfs_distances(engine.board, cop)

            def safety(move):
                cell = move.applied_to(me)
                exits = sum(1 for x in (Move.N, Move.S, Move.E, Move.W)
                            if engine.board.is_passable(x.applied_to(cell)))
                return (min(exits, 2), away.get(cell, 0))
            if moves:
                return protocol.move_action(max(moves, key=safety))
        target = self.stops[self._leg % len(self.stops)]
        if me == target:
            self._dwelt += 1
            if self._dwelt >= self.dwell_turns:
                self._leg, self._dwelt = self._leg + 1, 0
            return protocol.move_action(Move.STAY)
        path = bfs_distances(engine.board, target)
        if not moves:
            return protocol.move_action(Move.STAY)
        step = min(moves, key=lambda m: path.get(m.applied_to(me), 10**6))
        return protocol.move_action(step)
