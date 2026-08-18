"""League rehearsal: best2934's cop (gal-roy1 counted g01, 2026-08-16).

Their cop lost all three police windows of that counted series — gal-roy1's
fixed thief survived to 35 every time. This tape replays their cop's exact
recorded 36 steps (moves, barriers, hints, verbatim from their committed
artifact) through our REAL thief pipeline. Live fidelity notes: their cop
broadcasts a capture claim naming its own landing cell on every move turn
(ungated — strategy dossier), and on barrier turns the claim echoes the
barrier cell, which our wall-echo gate must drop; both behaviors are
reproduced here. Their cop is interactive (g01/g02/g03 scripts differ, unlike
their script-identical thief), so this pins one recorded instance, not the
policy — the bound is survival, not margin.
"""

import json
import random
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
_TAPE = json.loads(
    (Path(__file__).parent / "best2934_cop_tape_galroy_g01.json").read_text(
        encoding="utf-8"))
SEEDS = range(5)


def _cop_action(entry: dict):
    """Their record format: 'MOVE:E' | 'BARRIER:r,c' -> engine action."""
    move = entry["move"]
    if move.startswith("BARRIER:"):
        r, c = move.split(":", 1)[1].split(",")
        return {"type": "barrier", "cell": [int(r), int(c)]}, (int(r), int(c))
    return {"type": "move", "move": move.split(":", 1)[1]}, None


def play_tape(seed: int) -> tuple[Outcome, int]:
    """Their recorded cop, open loop, vs our live thief pipeline."""
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    config = Config.load("config")
    thief = ThiefBrain(Role.THIEF, random.Random(seed))
    percep = Perception.for_peer(Role.THIEF, config)
    entries = list(_TAPE) + [{"move": "MOVE:STAY", "hint": ""}] * 10
    for entry in entries:
        if engine.outcome is not Outcome.ONGOING:
            break
        action, barrier_cell = _cop_action(entry)
        try:
            protocol.apply_action(engine, Role.POLICE, action)
        except Exception:  # recorded wall now illegal in replay: hold instead
            protocol.apply_action(engine, Role.POLICE, {"type": "move", "move": "STAY"})
            barrier_cell = None
        if engine.outcome is not Outcome.ONGOING:
            break
        # their live claim broadcast: landing cell on moves, echo on barriers
        claim_cell = (barrier_cell if barrier_cell is not None
                      else tuple(engine.positions[Role.POLICE]))
        percep.observe(engine, Role.POLICE, entry.get("hint", ""),
                       barrier_cell=barrier_cell, claim_cell=claim_cell)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, percep.belief))
    return engine.outcome, engine.turns_completed


def test_their_recorded_cop_never_converts_us() -> None:
    """Every seed: our real thief survives the cop script that already
    failed against gal-roy1 — losing any seed here would mean we evade
    WORSE than the opponent they could not catch."""
    for seed in SEEDS:
        outcome, turns = play_tape(seed)
        assert outcome is Outcome.SURVIVAL, f"seed {seed}: {outcome} at {turns}"
