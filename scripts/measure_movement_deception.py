"""Does deception by movement pay? Feature-on vs feature-off, same seeds.

Self-play harness (static-duplicated arena, never cross-repo imports): OUR
StealthThiefBrain evades a BLIND cop that hunts through a BeliefMap fed by
the thief's scent and hint claims (the receiving side's own pipeline); the
cop's brain sees the believed thief cell, never the true one. Both arms run
the full lie policy (Deceiver), so the experiment also measures the
composition: does an already-ambiguous trail spend fewer lies? Arms differ
ONLY in [deception.movement] enabled.

Run: uv run python scripts/measure_movement_deception.py [games] [cop]
  cop: trap (scripted barrier cop, default) | deep (Double-DQN replay) |
       arena (pursuit-only baseline)
Output: results/experiments/movement_deception.json
"""

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.shared.config import Config
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.deception import Deceiver
from p2p_thief.strategy.movement_deception import StealthThiefBrain
from p2p_thief.strategy.thief_brain import CopForArena

RESULT_PATH = Path("results/experiments/movement_deception.json")
DEFAULT_GAMES = 60
COPS = {"trap": TrapCop, "deep": DeepTrapCop, "arena": CopForArena}


def believed_view(engine: GameEngine, belief: BeliefMap) -> SimpleNamespace:
    """The blind hunter's world: real board/rules/own cell, believed thief."""
    return SimpleNamespace(board=engine.board, rules=engine.rules,
                           positions={Role.POLICE: engine.positions[Role.POLICE],
                                      Role.THIEF: belief.argmax_cell()})


def _mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def play(seed: int, config: Config, movement_on: bool, cop_name: str) -> dict:
    rng = random.Random(seed)
    engine = GameEngine(config.grid_size, config.cop_start, config.thief_start,
                        config.rule_set())
    tuning = dict(config.deception()["movement"], enabled=movement_on)
    thief = StealthThiefBrain(Role.THIEF, rng, tuning=tuning)
    cop = COPS[cop_name](Role.POLICE, random.Random(seed + 999))
    cop_belief = BeliefMap(config.grid_size)    # the hunter's picture of us
    thief_belief = BeliefMap(config.grid_size)  # our picture of the hunter
    deceiver = Deceiver(Role.THIEF, config, rng)
    radius = config.deception()["exposure_radius"]
    turn, lies, track_errors, exposures = 0, 0, [], []
    while engine.outcome is Outcome.ONGOING:
        turn += 1
        protocol.apply_action(engine, Role.POLICE,
                              cop.decide(believed_view(engine, cop_belief)))
        if engine.outcome is not Outcome.ONGOING:
            break
        action = thief.decide(engine, thief_belief)
        claim, truth = deceiver.plan_hint(
            engine, SimpleNamespace(belief=thief_belief), Move[action["move"]], turn)
        lies += not truth
        protocol.apply_action(engine, Role.THIEF, action)  # closes the full turn
        deceiver.observe_own(engine, claim)
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
        cop_belief.observe_hint(claim, engine.scent[Role.THIEF])
        guess, me = cop_belief.argmax_cell(), engine.positions[Role.THIEF]
        track_errors.append(abs(guess[0] - me[0]) + abs(guess[1] - me[1]))
        exposures.append(deceiver.mirror.exposure(me, radius))
        thief_belief.diffuse(engine.board)
        thief_belief.observe_scent(engine.scent[Role.POLICE], engine.board)
    return {"outcome": engine.outcome, "lies": lies, "turns": engine.turns_completed,
            "track_error": _mean(track_errors), "exposure": _mean(exposures)}


def run_arm(config: Config, movement_on: bool, games: int, cop_name: str) -> dict:
    played = [play(seed, config, movement_on, cop_name) for seed in range(games)]
    survived = sum(game["outcome"] is Outcome.SURVIVAL for game in played)
    return {"games": games, "survival": survived, "capture": games - survived,
            "survival_rate": round(survived / games, 3),
            "mean_turns_survived": round(_mean([g["turns"] for g in played]), 2),
            "mean_lies_per_game": round(_mean([g["lies"] for g in played]), 2),
            "mean_cop_tracking_error": round(_mean([g["track_error"] for g in played]), 3),
            "mean_mirror_exposure": round(_mean([g["exposure"] for g in played]), 3)}


def main() -> None:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAMES
    cop_name = sys.argv[2] if len(sys.argv) > 2 else "trap"
    config = Config.load("config")
    report = {
        "description": "thief survival vs a blind belief-hunting cop, "
                       "movement deception on vs off (same seeds, lie policy on in both)",
        "opposition": cop_name,
        "movement_config": config.deception()["movement"],
        "off": run_arm(config, movement_on=False, games=games, cop_name=cop_name),
        "on": run_arm(config, movement_on=True, games=games, cop_name=cop_name),
    }
    report["survival_delta"] = round(
        report["on"]["survival_rate"] - report["off"]["survival_rate"], 3)
    report["tracking_error_delta"] = round(
        report["on"]["mean_cop_tracking_error"] - report["off"]["mean_cop_tracking_error"], 3)
    report["lies_saved_per_game"] = round(
        report["off"]["mean_lies_per_game"] - report["on"]["mean_lies_per_game"], 2)
    report["exposure_delta"] = round(
        report["on"]["mean_mirror_exposure"] - report["off"]["mean_mirror_exposure"], 3)
    if cop_name != "arena":  # honesty check vs the pursuit-only sparring cop too
        report["secondary_opposition"] = {
            "opposition": "arena",
            "off": run_arm(config, movement_on=False, games=games, cop_name="arena"),
            "on": run_arm(config, movement_on=True, games=games, cop_name="arena"),
        }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
