"""Sensitivity of the dwell-plateau fit gate (PRD 10), on the in-repo cop pool.

Sweeps `PLATEAU_MIN_FIT` and reports the precision/coverage trade-off the gate
buys when the THIEF localizes the hunter: how often a pin fires, how often it
is exactly right, and the mean error when it fires - against the posterior
argmax on the SAME turns as the control.

Ground truth is the arena's true cop cell; the thief stays blind and observes
through the shipped Perception pipeline.

Run: uv run python scripts/measure_localization.py [games_per_cop]
Output: results/experiments/plateau_localization.json
"""

import json
import random
import sys
from pathlib import Path

from p2p_thief.domain import evidence, protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.endgame import CertifiedThiefBrain
from p2p_thief.strategy.thief_brain import CopForArena

RESULT_PATH = Path("results/experiments/plateau_localization.json")
DEFAULT_GAMES = 20
COPS = {"blind_pursuit": CopForArena, "trap": TrapCop, "deep_trap": DeepTrapCop}
BLIND_COPS = {"blind_pursuit"}
FITS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def collect(seed: int, config: Config, cop_name: str) -> list[dict]:
    """One arena game; per turn, the truth, the pin and the argmax."""
    engine = GameEngine(config.grid_size, config.cop_start, config.thief_start,
                        config.rule_set())
    cop = COPS[cop_name](Role.POLICE, random.Random(seed))
    thief = CertifiedThiefBrain(Role.THIEF, random.Random(seed + 500))
    perception = Perception.for_peer(Role.THIEF, config)
    cop_belief = BeliefMap(config.grid_size)
    rows = []
    while engine.outcome is Outcome.ONGOING:
        view = cop_belief if cop_name in BLIND_COPS else None
        action = cop.decide(engine, view)
        wall = tuple(action["cell"]) if action["type"] == "barrier" else None
        protocol.apply_action(engine, Role.POLICE, action)
        if engine.outcome is not Outcome.ONGOING:
            break
        perception.observe(engine, Role.POLICE, None, barrier_cell=wall)
        truth = engine.positions[Role.POLICE]
        pins = {}
        for fit in FITS:
            evidence.PLATEAU_MIN_FIT = fit
            pin = evidence.plateau_origin(engine.scent[Role.POLICE], engine.board,
                                          config.grid_size)
            pins[str(fit)] = list(pin) if pin else None
        evidence.PLATEAU_MIN_FIT = 0.9  # restore the shipped gate
        peak = perception.belief.argmax_cell()
        rows.append({"truth": list(truth), "pins": pins,
                     "argmax_error": abs(peak[0] - truth[0]) + abs(peak[1] - truth[1])})
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, perception.belief))
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
    return rows


def summarize(rows: list[dict]) -> dict:
    turns = len(rows)
    table = {}
    for fit in FITS:
        fired = [r for r in rows if r["pins"][str(fit)] is not None]
        errors = [abs(r["pins"][str(fit)][0] - r["truth"][0])
                  + abs(r["pins"][str(fit)][1] - r["truth"][1]) for r in fired]
        table[str(fit)] = {
            "fire_rate": round(len(fired) / turns, 4) if turns else 0.0,
            "exact_when_fired": round(
                sum(1 for e in errors if e == 0) / len(errors), 4) if errors else None,
            "mean_error_when_fired": round(sum(errors) / len(errors), 3) if errors else None,
        }
    return {
        "turns": turns,
        "argmax_exact_rate": round(
            sum(1 for r in rows if r["argmax_error"] == 0) / turns, 4) if turns else 0.0,
        "argmax_mean_error": round(
            sum(r["argmax_error"] for r in rows) / turns, 3) if turns else None,
        "by_fit_threshold": table,
    }


def main() -> None:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAMES
    config = Config.load("config")
    rows = [row for name in COPS for seed in range(games)
            for row in collect(seed, config, name)]
    report = {
        "description": "dwell-plateau fit-gate sweep vs the posterior argmax, "
                       "blind thief, shipped Perception pipeline",
        "games_per_cop": games,
        "shipped_fit_threshold": 0.9,
        **summarize(rows),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
