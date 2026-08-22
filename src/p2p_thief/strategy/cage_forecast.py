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

NEAR_REACH = 2  # unanchored walls are feared only this close to the cop


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


def k_wall_region(board, landing, cop_cells, k, reach, quota) -> int:
    """The landing's reachable-region size under the WORST wall-set any
    believed cop could add: MIN over support cells and over every set of
    min(k, quota) sites within Manhattan `reach` of that cell."""
    walls = min(int(k), int(quota))
    if walls <= 0:
        return len(bfs_distances(board, landing))
    worst = board.grid_size * board.grid_size
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
