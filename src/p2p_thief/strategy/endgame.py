"""Survival certificate: an exact escape proof over the cop-belief support.

BELIEF-CORRECT (the thief never knows the true cop cell): a line is CERTIFIED
only when ONE move now survives every remaining turn against WORST-CASE cop
play - moves AND barriers - from EVERY cop cell carrying non-negligible
belief mass. The rival's true position is never read (guard-tested); domain
state stays read-only. Wired WITHOUT touching thief_brain.py: the [strategy]
seam points at CertifiedThiefBrain below, which composes the doctrine+
stealth brain for every turn the certificate cannot cover. Tunables come from
[strategy.endgame] (read directly here so no concurrently-owned module needs
editing); compute is hard-capped - a cap hit defers to the brain.
"""

import random
import time
import tomllib
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.board import Board
from p2p_thief.domain.primitives import Cell, Move, Role
from p2p_thief.strategy.doctrine import DoctrineThiefBrain

ORTHOGONAL = (Move.N, Move.S, Move.E, Move.W)
_MOVE_RANK = {move.name: rank for rank, move in enumerate((*ORTHOGONAL, Move.STAY))}
DEFAULTS: dict = {
    "enabled": False,              # keep-gate FAILED: 0 certificates in 180 games -
    #                                the scent-floor cop-belief never sharpens inside
    #                                the last-5-turns window (honest negative result,
    #                                docs/evidence/thief-certificate.md)
    "max_support_cells": 3,        # run only when the cop-belief support is sharp
    "support_mass_threshold": 0.05,  # cells at/above this mass form the support
    "max_horizon_turns": 5,        # certify only when it covers ALL turns left
    "node_cap": 20000,             # search states before deferring to the brain
    "time_cap_ms": 150.0,          # wall-clock cap - never risk the turn deadline
}


def certificate_settings(private: dict | None = None) -> dict:
    """[strategy.endgame] merged over DEFAULTS (type-coerced). private=None
    reads config/game.toml, so the seam-built wrapper stays config-driven."""
    if private is None:
        path = Path(__file__).resolve().parents[3] / "config" / "game.toml"
        private = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    block = private.get("strategy", {}).get("endgame", {})
    merged = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key in block:
            merged[key] = type(default)(block[key])
    return merged


class _BudgetError(Exception):
    """Node or time cap exhausted - the caller defers to the shipped brain."""


class _View:
    """Read-only board plus hypothetical barriers (domain is never mutated)."""

    def __init__(self, board: Board, extra: frozenset) -> None:
        self._board, self._extra = board, extra

    def is_passable(self, cell: Cell) -> bool:
        return cell not in self._extra and self._board.is_passable(cell)

    def is_surrounded(self, cell: Cell) -> bool:
        return all(not self.is_passable(m.applied_to(cell)) for m in ORTHOGONAL)


def support_cells(belief, threshold: float) -> list[Cell]:
    """Cells carrying non-negligible mass, read off a values() snapshot."""
    values = belief.values()
    return [(row, col) for row, masses in enumerate(values)
            for col, mass in enumerate(masses) if mass >= threshold]


class SurvivalCertificate:
    """Pre-check: a move PROVEN to survive out the clock, or None.

    Input: engine (read-only) + the thief's BeliefMap of the cop. Output: a
    protocol move action or None. Setup: a certificate_settings() table.
    """

    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.certified = 0  # measurement: turns this certificate decided

    def lock(self, engine, belief) -> dict | None:
        if not self.settings["enabled"] or belief is None:
            return None
        support = support_cells(belief, self.settings["support_mass_threshold"])
        if not 1 <= len(support) <= self.settings["max_support_cells"]:
            return None
        remaining = engine.rules.survival_threshold - engine.turns_completed
        if not 1 <= remaining <= int(self.settings["max_horizon_turns"]):
            return None  # a partial certificate proves nothing - cover it ALL
        me = engine.positions[Role.THIEF]
        quota = engine.rules.max_barriers - len(engine.board.barriers)
        self._memo: dict = {}
        self._nodes = 0
        self._deadline = time.monotonic() + self.settings["time_cap_ms"] / 1000.0
        try:
            certified: set | None = None
            for cop in support:
                safe = {m.name for m in (Move.STAY, *ORTHOGONAL) if self._move_survives(
                    m, me, cop, frozenset(), quota, remaining, engine.board)}
                certified = safe if certified is None else certified & safe
                if not certified:
                    return None
        except _BudgetError:
            return None
        self.certified += 1
        return protocol.move_action(Move[min(certified, key=_MOVE_RANK.__getitem__)])

    def _tick(self) -> None:
        self._nodes += 1
        if self._nodes > self.settings["node_cap"] or (
            self._nodes % 64 == 0 and time.monotonic() > self._deadline
        ):
            raise _BudgetError

    def _move_survives(self, move: Move, thief: Cell, cop: Cell, extra: frozenset,
                       quota: int, remaining: int, board: Board) -> bool:
        """Does `move` survive `remaining` full turns vs perfect cop play?"""
        self._tick()
        view = _View(board, extra)
        landed = move.applied_to(thief)
        if move is not Move.STAY and not view.is_passable(landed):
            return False
        if landed == cop or view.is_surrounded(landed):
            return False  # walked into the cop / rule 47 at the boundary
        if remaining <= 1:
            return True  # this boundary reaches the survival threshold
        for cop_move in (Move.STAY, *ORTHOGONAL):  # the cop's whole reply set
            target = cop_move.applied_to(cop)
            if cop_move is not Move.STAY and not view.is_passable(target):
                continue
            if target == landed or not self._survives(landed, target, extra, quota,
                                                      remaining - 1, board):
                return False
        if quota > 0:  # law of barriers: cop cell or an orthogonal neighbor
            for wall in (cop, *(m.applied_to(cop) for m in ORTHOGONAL)):
                if not (board.in_bounds(wall) and view.is_passable(wall)):
                    continue
                if wall == landed:
                    return False  # rule 46: walled where we stand
                walled = extra | {wall}
                if _View(board, walled).is_surrounded(landed) or not self._survives(
                        landed, cop, walled, quota - 1, remaining - 1, board):
                    return False
        return True

    def _survives(self, thief: Cell, cop: Cell, extra: frozenset,
                  quota: int, remaining: int, board: Board) -> bool:
        key = (thief, cop, extra, remaining)
        cached = self._memo.get(key)
        if cached is None:
            cached = any(
                self._move_survives(move, thief, cop, extra, quota, remaining, board)
                for move in (Move.STAY, *ORTHOGONAL)
            )
            self._memo[key] = cached
        return cached


class CertifiedThiefBrain(DoctrineThiefBrain):
    """Seam wrapper: certificate pre-check, else the doctrine+stealth brain."""

    def __init__(self, role: Role, rng: random.Random, private: dict | None = None) -> None:
        super().__init__(role, rng)
        self.certificate = SurvivalCertificate(certificate_settings(private))

    def decide(self, engine, belief=None) -> dict:
        if belief is not None:
            locked = self.certificate.lock(engine, belief)
            if locked is not None:
                return locked
        return super().decide(engine, belief)
