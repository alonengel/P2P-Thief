"""Survival certificate: certifies only what it can cover, refuses positions
the adversarial search refutes, defers on compute caps, and never reads the
rival's TRUE cell - the cop-belief support is its only source of candidates."""

import random
from pathlib import Path

from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.doctrine import DoctrineThiefBrain
from p2p_thief.strategy.endgame import (
    DEFAULTS,
    CertifiedThiefBrain,
    SurvivalCertificate,
    certificate_settings,
)
from p2p_thief.strategy.movement_deception import StealthThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


class FakeBelief:
    """Support-only belief stub: mass split evenly over chosen cells."""

    def __init__(self, grid_size: int, cells: list) -> None:
        self.grid_size, self._cells = grid_size, list(cells)

    def values(self) -> list[list[float]]:
        grid = [[0.0] * self.grid_size for _ in range(self.grid_size)]
        for row, col in self._cells:
            grid[row][col] = 1.0 / len(self._cells)
        return grid

    def argmax_cell(self):
        return self._cells[0]


def certificate(**overrides) -> SurvivalCertificate:
    return SurvivalCertificate({**DEFAULTS, "enabled": True, **overrides})


def with_turns_left(engine: GameEngine, left: int) -> GameEngine:
    engine.turns_completed = RULES.survival_threshold - left
    return engine


def coffin_engine() -> GameEngine:
    """Thief at (0,0), (1,0) walled, cop believed at (0,2): dead in two."""
    engine = GameEngine(7, (0, 2), (0, 0), RULES)
    engine.board.add_barrier((1, 0))
    engine.police_move(Move.STAY)  # hand the half-turn to the thief
    return engine


def test_settings_defaults_and_merge() -> None:
    assert DEFAULTS["enabled"] is True  # measured keep-gate verdict (re-opened)
    assert certificate_settings({}) == DEFAULTS
    table = certificate_settings({"strategy": {"endgame": {"node_cap": 9.0, "junk": 1}}})
    assert table["node_cap"] == 9 and isinstance(table["node_cap"], int)
    assert "junk" not in table
    assert set(certificate_settings(None)) == set(DEFAULTS)  # reads game.toml


def test_far_cop_position_is_certified() -> None:
    engine = with_turns_left(coffin_engine(), 2)
    action = certificate().lock(engine, FakeBelief(7, [(6, 6)]))  # cop believed far
    assert action is not None and action["type"] == "move"


def test_coffin_is_refused_the_search_refutes_it() -> None:
    """STAY dies to the (0,1) wall; E walks into the cop - nothing survives 2."""
    engine = with_turns_left(coffin_engine(), 2)
    assert certificate().lock(engine, FakeBelief(7, [(0, 2)])) is None


def test_final_turn_in_the_coffin_is_still_survivable() -> None:
    engine = with_turns_left(coffin_engine(), 1)
    assert certificate().lock(engine, FakeBelief(7, [(0, 2)])) is not None


def test_certificate_must_cover_every_support_cell() -> None:
    engine = with_turns_left(coffin_engine(), 2)
    assert certificate().lock(engine, FakeBelief(7, [(6, 6), (0, 2)])) is None


def test_horizon_gate_partial_certificates_prove_nothing() -> None:
    engine = with_turns_left(coffin_engine(), int(DEFAULTS["max_horizon_turns"]) + 1)
    assert certificate().lock(engine, FakeBelief(7, [(6, 6)])) is None


def test_node_cap_defers_to_the_brain() -> None:
    engine = with_turns_left(coffin_engine(), 2)
    capped = certificate(node_cap=1)
    assert capped.lock(engine, FakeBelief(7, [(6, 6)])) is None
    assert capped.certified == 0


def test_disabled_and_wide_support_defer() -> None:
    engine = with_turns_left(coffin_engine(), 2)
    assert SurvivalCertificate(dict(DEFAULTS, enabled=False)).lock(
        engine, FakeBelief(7, [(6, 6)])) is None
    spread = FakeBelief(7, [(6, 6), (5, 5), (4, 4), (3, 3)])
    assert certificate().lock(engine, spread) is None


def test_source_never_names_the_rival_position() -> None:
    source = Path("src/p2p_thief/strategy/endgame.py").read_text(encoding="utf-8")
    assert "Role.POLICE" not in source


class GuardedPositions(dict):
    """positions proxy that trips the moment anyone asks for the rival."""

    def __getitem__(self, role):
        assert role is not Role.POLICE, "live path read the rival's TRUE cell"
        return super().__getitem__(role)


def test_blind_decide_path_never_reads_rival_truth() -> None:
    engine = with_turns_left(coffin_engine(), 2)
    engine.positions = GuardedPositions(engine.positions)
    brain = CertifiedThiefBrain(Role.THIEF, random.Random(0))
    for support in ([(6, 6)], [(6, 6), (3, 3), (2, 5), (5, 1)]):  # locked + spread
        action = brain.decide(engine, FakeBelief(7, support))
        assert action["type"] == "move"


def test_wrapper_composes_the_stealth_brain_when_uncertified() -> None:
    """A refused certificate must hand the turn to the brain BENEATH the
    wrapper, untouched. Compared against DoctrineThiefBrain (its actual
    super, which is itself a StealthThiefBrain — pinned by the seam test
    below): pure-stealth equality was rng-order-luck, since inside a coffin
    every cramped cell scores alike and the doctrine layer breaks the tie."""
    engine = with_turns_left(coffin_engine(), 2)
    belief = FakeBelief(7, [(0, 2)])  # refused above -> falls through
    wrapped = CertifiedThiefBrain(Role.THIEF, random.Random(7)).decide(engine, belief)
    beneath = DoctrineThiefBrain(Role.THIEF, random.Random(7)).decide(engine, belief)
    assert wrapped == beneath
    assert isinstance(DoctrineThiefBrain(Role.THIEF, random.Random(7)),
                      StealthThiefBrain)


def test_seam_wrapper_keeps_movement_deception_armed() -> None:
    """Regression: pointing [strategy] at the certificate wrapper must never
    silently drop the stealth layer (certificate rides ON TOP of it)."""
    brain = CertifiedThiefBrain(Role.THIEF, random.Random(0))
    assert isinstance(brain, StealthThiefBrain)
    assert hasattr(brain, "estimator") and hasattr(brain, "certificate")
