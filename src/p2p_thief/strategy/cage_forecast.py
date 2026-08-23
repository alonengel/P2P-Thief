"""The k-wall cage forecast: price a FORMING multi-wall cage while its
gap still exists (mechanism studied from imreeyal, re-implemented, no
code copied - ADR-0013).

The one-ply worst-wall probe sees only the cage's LAST wall; a builder
that lays a column then seals a row kills between those checks (najamjad
2026-08-22: an 11-wall quadrant script, byte-identical across three
games, converted our fielded thief at t27, 0/15). The barrier law
confines each placement to the placer's cell and orthogonal neighbours,
so the trap game is exactly computable: enumerate every wall-SET of size
min(k, quota) placeable within `reach` of each believed cop cell and
take the landing's WORST reachable region. The budget clamps to the
cop's live quota - a cage needing more walls than remain is not feared
(imreeyal's measured trade: k=4 lifted survival 16/32 -> 31/32 vs
builders and costs survival vs pure interception cops, so the knob
ships per-pairing, never a hard default).
"""

from itertools import combinations

from p2p_thief.domain.pathfind import bfs_distances

NEAR_REACH = 3  # unanchored walls are feared this close to the cop (counted
#                 g02: the row-seal cells sat at distance 2-3, unanchored,
#                 when the side still had free crossings - reach 2 missed them)


SITE_CAP = 14  # C(14,4)=1001 wall-sets: the compute keeps a turn budget


def _anchored(board, cell):
    """Adjacent to an existing barrier or on the rim: where a line-
    builder's next wall extends structure into a cut (imreeyal's
    accretion insight - scattered pillars cage nobody, and every cut
    ENDS at a rim, so line-ends are rim cells)."""
    r, c = cell
    if r in (0, board.grid_size - 1) or c in (0, board.grid_size - 1):
        return True
    return any(board.is_barrier((r + dr, c + dc))
               for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _sites(board, cop, reach, landing):
    r0, c0 = cop
    cells = [
        (r, c)
        for r in range(max(0, r0 - reach), min(board.grid_size, r0 + reach + 1))
        for c in range(max(0, c0 - reach), min(board.grid_size, c0 + reach + 1))
        if abs(r - r0) + abs(c - c0) <= reach and board.is_passable((r, c))
        and (abs(r - r0) + abs(c - c0) <= NEAR_REACH or _anchored(board, (r, c)))
    ]
    # The walls that cage THIS landing sit near its region boundary: keep
    # the nearest SITE_CAP so the enumeration stays inside a turn budget.
    cells.sort(key=lambda s: abs(s[0] - landing[0]) + abs(s[1] - landing[1]))
    return cells[:SITE_CAP]


class _Walled:
    def __init__(self, board, extra):
        self._board, self._extra, self.grid_size = board, extra, board.grid_size

    def is_passable(self, cell):
        return cell not in self._extra and self._board.is_passable(cell)


def _runs(board):
    """Maximal colinear barrier runs of length >= 3: a line-builder's
    DECLARED cut (najamjad counted g02, 2026-08-23: three column walls
    by their step 7, every crossing still free - the side gets picked
    then, not when the last gap is guarded)."""
    for horizontal in (False, True):
        for i in range(board.grid_size):
            run = 0
            for j in range(board.grid_size + 1):
                cell = ((i, j) if horizontal else (j, i))
                if j < board.grid_size and board.is_barrier(cell):
                    run += 1
                    continue
                if run >= 3:
                    yield (i, horizontal)
                run = 0


def completion_extra(board, quota) -> frozenset | None:
    """The hypothetical walls that finish every declared cut, or None
    when no cut exists / the builder lacks the quota to finish."""
    extra = set()
    for i, horizontal in _runs(board):
        line = [((i, j) if horizontal else (j, i))
                for j in range(board.grid_size)]
        extra.update(c for c in line if board.is_passable(c))
    if not extra or len(extra) > int(quota):
        return None
    return frozenset(extra)


def line_completion_region(board, landing, quota) -> int:
    """The landing's reachable region with every declared cut COMPLETED
    to both rims (all runs together, quota-clamped: a builder without
    the walls to finish its lines cages nobody)."""
    extra = completion_extra(board, quota)
    if extra is None:
        return len(bfs_distances(board, landing))
    return len(bfs_distances(_Walled(board, extra - {landing}), landing))


def doctrine_room(doctrine: dict, support, engine, cell) -> int:
    """The doctrine's cage rank: k_wall_region under the live quota, or
    the inert 0 when the knob is off / the support is empty."""
    if not (doctrine["forecast_walls"] and support):
        return 0
    quota = engine.rules.max_barriers - len(engine.board.barriers)
    return k_wall_region(engine.board, cell, support,
                         doctrine["forecast_walls"],
                         doctrine["forecast_wall_reach"], quota)


def arm_builder_escape(brain, engine) -> None:
    """A DECLARED CUT (3+ colinear walls) is a cage being built: aim the
    brain's DOMINANT escape at the best cell of the largest completed-
    projection room, re-aimed every turn while the cut stands — the side
    gets picked while every crossing is still free (counted g02
    2026-08-23 t31: flee alone herded us into the pocket that then
    sealed under guard). Already standing in the largest room arms
    nothing; non-builders never reach here."""
    quota = engine.rules.max_barriers - len(engine.board.barriers)
    extra = completion_extra(engine.board, quota)
    if extra is None:
        return
    me = engine.positions[brain.role]
    # Tie-break by cop distance (live counted g02 x3, t31 each: a full
    # column splits the rooms 21-21, a strictly-greater-room rule never
    # armed, and the counter structurally could not fire). Equal rooms
    # resolve AWAY from the believed cop: a cop hunting our half arms
    # the crossing while the gaps are free; a cop in the far half arms
    # nothing. Empty support degrades to pure room (the old rule).
    cops = list(getattr(brain, "_support", None) or [])

    def cop_gap(cell):
        if not cops:
            return 0
        return min(abs(cell[0] - c[0]) + abs(cell[1] - c[1]) for c in cops)

    mine = bfs_distances(_Walled(engine.board, extra - {me}), me)
    best, target = (len(mine), cop_gap(me)), None
    for cell, _steps in sorted(bfs_distances(engine.board, me).items(),
                               key=lambda kv: kv[1]):
        if cell in extra or cell in mine:
            # never target our own projected room: the escape exists for
            # CROSSINGS - intra-room flight is the far-corner herding the
            # whole mechanism is built to prevent
            continue
        room = len(bfs_distances(_Walled(engine.board, extra - {cell}), cell))
        key = (room, cop_gap(cell))
        if key > best:  # nearest-first scan: first strict win stays
            best, target = key, cell
    if target is not None:
        brain._escape_until = (engine.turns_completed
                               + brain.doctrine["escape_turns"])
        brain._escape_dist = bfs_distances(engine.board, target)


def k_wall_region(board, landing, cop_cells, k, reach, quota) -> int:
    """The landing's reachable-region size under the WORST wall-set any
    believed cop could add: MIN over support cells and over every set of
    min(k, reach) sites within Manhattan `reach` of that cell — floored
    by the line-completion projection (a declared cut completes)."""
    completed = line_completion_region(board, landing, quota)
    walls = min(int(k), int(quota))
    if walls <= 0:
        return min(completed, len(bfs_distances(board, landing)))
    worst = completed
    for cop in cop_cells:
        sites = [s for s in _sites(board, cop, reach, landing) if s != landing]
        for wall_set in combinations(sites, min(walls, len(sites))):
            view = _Walled(board, frozenset(wall_set))
            room = len(bfs_distances(view, landing))
            if room < worst:
                worst = room
                if worst <= 1:
                    return worst  # caged outright: no deeper worst exists
    return worst
