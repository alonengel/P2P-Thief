"""Strategy tests: the [strategy] seam resolves configured brains, the shipped
pursuit brain wins the PRD-03 arena milestone (beats a random thief), and
brain actions are always legal."""

import random
from pathlib import Path

import pytest

from p2p_thief.domain import protocol
from p2p_thief.domain.board import Board
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances, distance_between
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.shared.config import Config
from p2p_thief.strategy.brain_base import BrainBase, RandomBrain, resolve_brain
from p2p_thief.strategy.thief_brain import CopForArena, ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)


def test_bfs_respects_barriers() -> None:
    board = Board(7)
    assert distance_between(board, (0, 0), (0, 2)) == 2
    board.add_barrier((0, 1))
    assert distance_between(board, (0, 0), (0, 2)) == 4  # around the wall


def test_bfs_unreachable_when_walled_off() -> None:
    board = Board(7)
    for cell in [(0, 1), (1, 1), (1, 0)]:
        board.add_barrier(cell)
    assert distance_between(board, (0, 0), (6, 6)) == -1
    assert (6, 6) not in bfs_distances(board, (0, 0))


def play_arena(police_brain: BrainBase, thief_brain: BrainBase) -> Outcome:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    while engine.outcome is Outcome.ONGOING:
        actor = engine.next_actor
        brain = police_brain if actor is Role.POLICE else thief_brain
        protocol.apply_action(engine, actor, brain.decide(engine))
    return engine.outcome


def test_evasion_brain_survives_random_cop_at_least_80_percent() -> None:
    """PRD-03 milestone (thief side)."""
    survivals = 0
    for seed in range(25):
        outcome = play_arena(
            RandomBrain(Role.POLICE, random.Random(seed + 1000)),
            ThiefBrain(Role.THIEF, random.Random(seed)),
        )
        survivals += outcome is Outcome.SURVIVAL
    assert survivals >= 20, f"evasion brain survived only {survivals}/25 random cops"


def test_evasion_vs_pursuing_arena_cop_completes_legally() -> None:
    """Sanity vs a real pursuer (the true police brain lives in the twin
    repo): games complete legally; dominance is not asserted here."""
    for seed in range(5):
        outcome = play_arena(
            CopForArena(Role.POLICE, random.Random(seed + 7)),
            ThiefBrain(Role.THIEF, random.Random(seed)),
        )
        assert outcome in (Outcome.CAPTURE, Outcome.SURVIVAL)


def test_resolve_brain_defaults_to_shipped_thief_brain(config_dir: Path) -> None:
    config = Config.load(config_dir)
    assert isinstance(resolve_brain(config, Role.THIEF, random.Random(0)), ThiefBrain)


def test_resolve_brain_honors_strategy_override(config_dir: Path) -> None:
    toml_path = config_dir / "game.toml"
    toml_path.write_text(
        toml_path.read_text(encoding="utf-8")
        + '\n[strategy]\nthief_class = "p2p_thief.strategy.brain_base:RandomBrain"\n',
        encoding="utf-8",
    )
    config = Config.load(config_dir)
    assert isinstance(resolve_brain(config, Role.THIEF, random.Random(0)), RandomBrain)


def test_resolve_brain_surfaces_bad_spec_loudly(config_dir: Path) -> None:
    toml_path = config_dir / "game.toml"
    toml_path.write_text(
        toml_path.read_text(encoding="utf-8")
        + '\n[strategy]\nthief_class = "no.such.module:Nope"\n',
        encoding="utf-8",
    )
    config = Config.load(config_dir)
    with pytest.raises(ModuleNotFoundError):
        resolve_brain(config, Role.THIEF, random.Random(0))
