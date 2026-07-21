"""Policy-vs-coin measurement: does the self-mirror lie policy buy survival?

Self-play harness (static-duplicated arena, never cross-repo imports): OUR
ThiefBrain evades the arena pursuit cop; the cop hunts through a BeliefMap
fed by the thief's scent and hint claims (the receiving side's own update
pipeline). Arm "coin" hints by the config baseline_truth_probability; arm
"policy" by the Deceiver. Same seeds per arm — only the hint policy varies.

Run: uv run python scripts/measure_deception.py [games]
Output: results/experiments/deception_policy.json
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
from p2p_thief.strategy.deception import Deceiver
from p2p_thief.strategy.hints import build_hint
from p2p_thief.strategy.thief_brain import CopForArena, ThiefBrain

RESULT_PATH = Path("results/experiments/deception_policy.json")
DEFAULT_GAMES = 60


def play(seed: int, config: Config, use_policy: bool) -> dict:
    rng = random.Random(seed)
    engine = GameEngine(config.grid_size, config.cop_start, config.thief_start,
                        config.rule_set())
    thief = ThiefBrain(Role.THIEF, rng)
    cop = CopForArena(Role.POLICE, random.Random(seed + 999))
    cop_belief = BeliefMap(config.grid_size)    # the hunter's picture of us
    thief_belief = BeliefMap(config.grid_size)  # our picture of the hunter
    deceiver = Deceiver(Role.THIEF, config, rng)
    coin = config.deception()["baseline_truth_probability"]
    max_words = int(config.shared["world"]["hint_max_words"])
    turn, lies, track_errors = 0, 0, []
    while engine.outcome is Outcome.ONGOING:
        turn += 1
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine, cop_belief))
        if engine.outcome is not Outcome.ONGOING:
            break
        action = thief.decide(engine, thief_belief)
        move = Move[action["move"]]
        if use_policy:
            claim, truth = deceiver.plan_hint(
                engine, SimpleNamespace(belief=thief_belief), move, turn)
        else:
            _, claim, truth = build_hint(move, rng.random() < coin, max_words, rng)
        lies += not truth
        protocol.apply_action(engine, Role.THIEF, action)  # closes the full turn
        if use_policy:
            deceiver.observe_own(engine, claim)
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
        cop_belief.observe_hint(claim, engine.scent[Role.THIEF])
        guess, me = cop_belief.argmax_cell(), engine.positions[Role.THIEF]
        track_errors.append(abs(guess[0] - me[0]) + abs(guess[1] - me[1]))
        thief_belief.diffuse(engine.board)
        thief_belief.observe_scent(engine.scent[Role.POLICE], engine.board)
    return {"outcome": engine.outcome, "lies": lies,
            "track_error": sum(track_errors) / max(1, len(track_errors))}


def run_arm(config: Config, use_policy: bool, games: int) -> dict:
    played = [play(seed, config, use_policy) for seed in range(games)]
    survived = sum(game["outcome"] is Outcome.SURVIVAL for game in played)
    return {"games": games, "survival": survived, "capture": games - survived,
            "survival_rate": round(survived / games, 3),
            "mean_lies_per_game": round(sum(g["lies"] for g in played) / games, 2),
            "mean_cop_tracking_error": round(
                sum(g["track_error"] for g in played) / games, 3)}


def main() -> None:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAMES
    config = Config.load("config")
    report = {
        "description": "thief survival vs belief-driven arena cop, per hint policy",
        "deception_config": config.deception(),
        "coin": run_arm(config, use_policy=False, games=games),
        "policy": run_arm(config, use_policy=True, games=games),
    }
    report["survival_delta"] = round(
        report["policy"]["survival_rate"] - report["coin"]["survival_rate"], 3)
    report["lies_saved_per_game"] = round(
        report["coin"]["mean_lies_per_game"] - report["policy"]["mean_lies_per_game"], 2)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
