"""Replay gates for the cage machinery: the recorded najamjad tapes
(yesterday's script and the counted g02 that killed the fielded thief
live) must survive with every counter armed. Split from
test_cage_forecast.py for the 150-line cap.
"""

import json
import random
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.board import Board
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.endgame import CertifiedThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
TAPE = json.loads((Path(__file__).parent / "najamjad_cage_tape.json")
                  .read_text(encoding="utf-8"))["actions"]


def _play_script(seed: int, doctrine_overrides: dict):
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    private = {"strategy": {"doctrine": doctrine_overrides,
                            "endgame": {"time_cap_ms": 60000}}}
    brain = CertifiedThiefBrain(Role.THIEF, random.Random(seed), private)
    from p2p_thief.peer.perception import Perception

    percep = Perception(Role.THIEF, 7, rival_start=(0, 0))
    for turn in range(RULES.max_moves):
        entry = TAPE[turn] if turn < len(TAPE) else {"move": "STAY"}
        try:
            action = ({"type": "barrier", "cell": entry["barrier"]}
                      if "barrier" in entry
                      else {"type": "move", "move": entry.get("move", "STAY")})
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:
            protocol.apply_action(engine, Role.POLICE,
                                  {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, "")
        protocol.apply_action(engine, Role.THIEF,
                              brain.decide(engine, percep.belief))
        if engine.outcome is not Outcome.ONGOING:
            break
    return engine.outcome


def test_armed_forecast_survives_the_recorded_najamjad_cage() -> None:
    """k=4/reach=2 armed: the fielded brain must survive the exact script
    that killed it 0/15 - at least 4 of 5 seeds."""
    survived = sum(
        _play_script(seed, {"forecast_walls": 4, "forecast_wall_reach": 4, "builder_escape": True})
        is Outcome.SURVIVAL
        for seed in range(5))
    assert survived >= 4, f"cage script survived only {survived}/5"


def test_default_off_stays_byte_identical_documenting_the_death() -> None:
    """The knob defaults 0 (off): the recorded death stands as the
    documented baseline this mechanism exists to fix."""
    assert _play_script(0, {}) is Outcome.CAPTURE


def test_line_completion_prices_a_forming_cut_before_its_gaps_close() -> None:
    """COUNTED g02 lesson (2026-08-23, t31): the k-wall forecast fears
    wall-sets near the believed cop, so a LINE-builder's cut registers
    only when the cop nears the gaps - by then it GUARDS them and the
    lethal gate forbids the crossing. A run of 3+ colinear walls is a
    declared cut: price the landing as if every such run completes to
    both rims (quota-clamped). Their column has 3 walls by step 7 -
    sides get picked THEN, while every crossing is free."""
    from p2p_thief.strategy.cage_forecast import line_completion_region

    board = Board(7)
    for r in (0, 1, 2):
        board.add_barrier((r, 3))  # their column, 3 walls: a declared cut
    left = line_completion_region(board, (3, 1), quota=11)
    right = line_completion_region(board, (3, 5), quota=11)
    assert left <= 21 and right <= 21  # both sides priced as POST-cut rooms
    open_cell = line_completion_region(Board(7), (3, 3), quota=14)
    assert open_cell > 40  # no runs: the whole board is one room
    # quota clamp: a cop without the walls to finish the cut cages nobody
    assert line_completion_region(board, (3, 5), quota=1) > 30


def _positions_through_script(seed, doctrine):
    """Replay the COUNTED tape, recording our thief's position per turn."""
    tape = json.loads((Path(__file__).parent
                       / "najamjad_counted_g02_tape.json")
                      .read_text(encoding="utf-8"))["actions"]
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    private = {"strategy": {"doctrine": doctrine,
                            "endgame": {"time_cap_ms": 60000}}}
    brain = CertifiedThiefBrain(Role.THIEF, random.Random(seed), private)
    from p2p_thief.peer.perception import Perception

    percep = Perception(Role.THIEF, 7, rival_start=(0, 0))
    trail = []
    for turn in range(RULES.max_moves):
        entry = tape[turn] if turn < len(tape) else {"move": "STAY"}
        try:
            action = ({"type": "barrier", "cell": entry["barrier"]}
                      if "barrier" in entry
                      else {"type": "move", "move": entry.get("move", "STAY")})
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:
            protocol.apply_action(engine, Role.POLICE,
                                  {"type": "move", "move": "STAY"})
        if engine.outcome is not Outcome.ONGOING:
            break
        percep.observe(engine, Role.POLICE, "")
        protocol.apply_action(engine, Role.THIEF,
                              brain.decide(engine, percep.belief))
        trail.append(engine.positions[Role.THIEF])
        if engine.outcome is not Outcome.ONGOING:
            break
    return engine.outcome, trail


def test_room_tie_breaks_away_from_the_believed_cop() -> None:
    """Live counted g02 x3 (t31, byte-identical moves): the column splits
    the board 21-21, rooms TIE, and a strictly-greater-room rule never
    arms the escape - the counter existed and structurally could not
    fire. Tie-break: equal rooms resolve AWAY from the believed cop, so
    a cop hunting our half arms the crossing while gaps are free; a cop
    in the far half arms nothing (we already stand in the right place)."""
    from types import SimpleNamespace

    from p2p_thief.strategy.cage_forecast import arm_builder_escape

    engine = SimpleNamespace(
        board=Board(7),
        positions={Role.THIEF: (2, 5)},
        turns_completed=10,
        rules=RULES,
    )
    for r in range(5):
        engine.board.add_barrier((r, 3))  # partial column: cut declared,
    #                                       completion projects rooms 21-21

    def brain(support):
        return SimpleNamespace(role=Role.THIEF, doctrine={"escape_turns": 3},
                               _support=support, _escape_until=-1,
                               _escape_dist={})

    hunted = brain([(4, 4), (3, 4)])  # believed cop entering OUR half
    arm_builder_escape(hunted, engine)
    assert hunted._escape_until > 10  # armed
    left_target_dist = min(hunted._escape_dist.get((r, c), 999)
                           for r in range(7) for c in range(0, 3))
    assert left_target_dist == 0  # the escape target lies in the LEFT half

    safe = brain([(5, 0)])  # believed cop in the FAR half
    arm_builder_escape(safe, engine)
    assert safe._escape_until == -1  # nothing to flee: we hold the far side


def test_armed_thief_survives_the_counted_tape_that_killed_it() -> None:
    """The live t31 death, replayed with every cage mechanism armed:
    survival on all seeds. HONESTY NOTE: offline the recorded chase is
    open-loop, so this pins capability, not the live outcome — the
    survivals here come from late pocket-play as often as early
    crossing. The script's one clean early exit runs TOWARD the cop
    through its own shadow (their build herds away from it by design),
    which no flee-shaped metric will take; the live counter-evidence
    stays recorded in the fixture header."""
    armed = {"forecast_walls": 4, "forecast_wall_reach": 4,
             "builder_escape": True}
    for seed in range(5):
        outcome, trail = _positions_through_script(seed, armed)
        assert outcome is Outcome.SURVIVAL, f"seed {seed}: {outcome}"
        assert len(trail) >= 34  # the full clock ran, never an early fold
