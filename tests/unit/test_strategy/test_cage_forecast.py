"""The k-wall cage forecast: pricing a FORMING multi-wall cage while its
gap still exists (mechanism studied from imreeyal, re-implemented, no
code copied - ADR-0013; their measured verdict: 16/32 -> 31/32 survival
vs wall-builders at k=4).

The red fixture is real: najamjad's 2026-08-22 cop script (revealed
records, g02 - byte-identical across three games, so provably open-loop)
walls column 3 top-down then seals row 3 across, and our fielded thief
died to it at t27, 0/15 seeds. The one-ply forecast cannot see a cage
that needs three more walls; this one must.
"""

import json
from pathlib import Path

from p2p_thief.domain.board import Board
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.cage_forecast import k_wall_region

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
TAPE = json.loads((Path(__file__).parent / "najamjad_cage_tape.json")
                  .read_text(encoding="utf-8"))["actions"]


def test_open_board_k_region_is_large_everywhere() -> None:
    board = Board(7)
    room = k_wall_region(board, (3, 3), [(0, 0)], k=4, reach=2, quota=14)
    assert room > 20  # four walls near a far corner cannot cage the center


def test_half_built_column_prices_the_closing_side_down() -> None:
    """Column 3 walled rows 0-4, cop at (5,3) with quota: the k-set can
    finish the cut. A cell deep in either half keeps its half's room;
    a cell ON the closing seam prices near-caged."""
    board = Board(7)
    for r in range(5):
        board.add_barrier((r, 3))
    seam = k_wall_region(board, (5, 3 + 1), [(5, 3)], k=4, reach=2, quota=9)
    deep = k_wall_region(board, (1, 5), [(5, 3)], k=4, reach=2, quota=9)
    assert seam < deep  # hugging the closing gap is priced as the trap it is


def test_quota_clamps_the_feared_walls() -> None:
    board = Board(7)
    with_quota = k_wall_region(board, (3, 4), [(3, 3)], k=4, reach=2, quota=4)
    no_quota = k_wall_region(board, (3, 4), [(3, 3)], k=4, reach=2, quota=0)
    assert no_quota >= with_quota  # a cop out of walls cages nothing
