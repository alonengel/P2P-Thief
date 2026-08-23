"""LIVE-FAITHFUL replay gate for the najamjad counted series 2 (2026-08-23
evening, seeds 260825/260827/260829: captured t31 in all three windows).

The GameEngine harness in test_cage_tapes.py under-sharpens belief (engine
scent lags one round and the cadence is cop-first), so the armed brain
"survived" the same tape there while dying live. This harness rebuilds the
REFERENCE-wire thief exactly: OwnState, thief-first cadence, and the cop's
TRANSMITTED scent frames — najamjad emits at its post-move cell every step,
verified byte-identical (max abs error 0.0 over all 31 recorded frames of
results/log_anrbj666-vs-najamjad_g02.json) to our ScentField updated per
cop step. Under those inputs the belief peak pins at >= SHARP_BELIEF, the
trusted-sharp branch runs, and (pre-fix) the whole cage doctrine was
bypassed — the recorded death reproduces move-for-move.
"""

import json
import random
from pathlib import Path

from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.domain.scent import ScentField
from p2p_thief.peer.perception import Perception
from p2p_thief.strategy.endgame import CertifiedThiefBrain
from p2p_thief.wire.own_state import OwnState

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
TAPE = json.loads((Path(__file__).parent / "najamjad_counted2_tape.json")
                  .read_text(encoding="utf-8"))["actions"]
ARMED = {"forecast_walls": 4, "forecast_wall_reach": 4, "builder_escape": True}


def _play_live(seed: int, doctrine: dict):
    """Replay the recorded cop against our thief on the live wire shape."""
    own = OwnState(Role.THIEF, 7, (3, 3), RULES)
    private = {"strategy": {"doctrine": doctrine,
                            "endgame": {"time_cap_ms": 60000}}}
    brain = CertifiedThiefBrain(Role.THIEF, random.Random(seed), private)
    percep = Perception(Role.THIEF, 7, rival_start=(0, 0))
    cop_field, cop = ScentField(7), (0, 0)
    trail: list = []
    for their_step in range(RULES.max_moves + 1):
        # ---- thief half-turn (the reference wire's thief opens rounds) ----
        action = brain.decide(own, percep.belief)
        own.apply_own_action(action)
        trail.append(own.cell)
        if own.i_am_captured() or own.cell == cop:
            return "capture", own.turns_completed + 1, trail
        own.close_full_turn()
        if own.survival_reached():
            return "survival", own.turns_completed, trail
        # ---- cop half-turn from the tape (open-loop: frames stay valid) ----
        entry = TAPE[their_step] if their_step < len(TAPE) else {"move": "STAY"}
        bcell = tuple(entry["barrier"]) if "barrier" in entry else None
        if bcell is not None:
            own.note_rival_barrier(bcell)
        else:
            cop = Move[entry.get("move", "STAY")].applied_to(cop)
        cop_field.update(cop)  # najamjad emits per step at its post-move cell
        own.scent[Role.POLICE].absorb({
            f"{r},{c}": v for r, row in enumerate(cop_field.values())
            for c, v in enumerate(row) if v > 0.0})
        own.note_rival_half_turn()
        percep.observe(own, Role.POLICE, "", barrier_cell=bcell)
        if (bcell is not None and bcell == own.cell) or cop == own.cell:
            return "capture", own.turns_completed, trail
    return "survival", own.turns_completed, trail


def test_armed_thief_survives_the_live_faithful_counted2_replay() -> None:
    """The 2026-08-23 counted deaths, replayed on the live wire shape with
    every cage mechanism armed: survival at the three counted seeds. Before
    the trusted-sharp fix this reproduced the t31 capture at (2,4)
    move-for-move on every seed."""
    for seed in (260825, 260827, 260829):
        outcome, turns, trail = _play_live(seed, ARMED)
        assert outcome == "survival", (
            f"seed {seed}: {outcome} at t{turns}, final {trail[-1]}")
        assert turns >= 35


def test_armed_survival_holds_across_generic_seeds() -> None:
    """Seed-robustness: the survival must not hinge on one rng stream."""
    for seed in range(5):
        outcome, turns, trail = _play_live(seed, ARMED)
        assert outcome == "survival", (
            f"seed {seed}: {outcome} at t{turns}, final {trail[-1]}")


def test_default_off_documents_the_live_death() -> None:
    """Knobs off must stay byte-identical: on the live wire shape the
    unarmed brain dies exactly as the fielded one did (t31, herded into
    the NE pocket's dead end). The recorded baseline this fix exists for."""
    outcome, turns, _trail = _play_live(260825, {})
    assert outcome == "capture" and turns == 31
