"""Guard: the committed sparring posture is GENERIC play — uncounted warm-ups
must not leak our tuned play into a rival's cross-game profiler before a
counted series (loaded by `peer --sparring` instead of game.toml)."""

import random
from pathlib import Path

import pytest

from p2p_thief.domain.primitives import Role
from p2p_thief.shared.config import Config, ConfigError
from p2p_thief.shared.interlock import assert_sparring_posture
from p2p_thief.strategy.brain_base import resolve_brain
from p2p_thief.strategy.thief_brain import ThiefBrain
from p2p_thief.wire import lock

ROOT = Path(__file__).resolve().parents[3]


def load_sparring() -> Config:
    return Config.load(ROOT / "config", private_file="sparring.toml")


def test_sparring_runs_the_shipped_baseline_brain_only() -> None:
    config = load_sparring()
    assert "strategy" not in config.private  # no class override, no tuned weights
    brain = resolve_brain(config, Role.THIEF, random.Random(0))
    # the plain baseline brain: sparring layers on no wrapper of any kind
    assert type(brain) is ThiefBrain


def test_sparring_disarms_deception_and_tuned_terms() -> None:
    config = load_sparring()
    tuning = config.deception()
    assert tuning["max_lies"] == 0  # zero lie budget: every hint truthful
    assert tuning["movement"]["enabled"] is False  # stealth movement term off
    # The invariant is that sparring carries no OVERRIDES: no [strategy] table,
    # so no wrapper is ever built and the certificate cannot run whatever the
    # shipped default says (pinned by the brain-type assertion above).
    assert "endgame" not in config.private.get("strategy", {})


def test_sparring_emails_nothing() -> None:
    config = load_sparring()
    assert "email" not in config.private  # no recipient, no mode: series email no-ops


def test_sparring_wire_shape_is_selectable() -> None:
    config = load_sparring()
    # Committed default is the league wire since fad7113 (cross-team warm-ups
    # all speak reference-v3); the --wire-shape seam still selects bookletter.
    assert lock.wire_shape(config) == lock.REFERENCE
    config.private["network"]["wire_shape"] = "bookletter"
    assert lock.wire_shape(config) == lock.BOOKLETTER


def test_sparring_identity_stays_real() -> None:
    # Rule 45 + team identity: warm-ups still declare who we really are.
    assert load_sparring().group_id == Config.load(ROOT / "config").group_id


def test_load_time_assertion_accepts_the_committed_sparring_file() -> None:
    """The structural gate `peer --sparring` runs at load must accept the
    posture we actually ship (guards the file against future drift)."""
    assert_sparring_posture(load_sparring().private)  # must not raise


def test_load_time_assertion_refuses_a_tuned_strategy_table() -> None:
    with pytest.raises(ConfigError, match=r"\[strategy\]"):
        assert_sparring_posture({"strategy": {"thief_class": "pkg.mod:Cls"}})
    with pytest.raises(ConfigError, match=r"\[strategy\]"):
        assert_sparring_posture({"strategy": {"endgame": {"enabled": True}}})


def test_load_time_assertion_refuses_an_armed_email_path() -> None:
    with pytest.raises(ConfigError, match="never emails"):
        assert_sparring_posture({"email": {"mode": "send", "recipient": "x@example.com"}})
    assert_sparring_posture({"email": {"mode": "disabled"}})  # disabled plays
    assert_sparring_posture({})  # absent plays
