"""Keep-gate arena: does the survival certificate keep the THIEF alive?

Arms (same seeds): the shipped brain with the certificate pre-check OFF vs
ON - the same class both ways, so the delta isolates the certificate and
nothing else - against the arena cop pool: TrapCop (scripted wall-builder)
and DeepTrapCop (the twin-trained Double-DQN cop), both FULL information (the
harshest hunters we own), plus blind pursuit (the realistic league condition).
The thief is always BLIND and observes through the SHIPPED Perception
pipeline, so the belief measured here is the belief that plays. Keep rule:
the certificate stays enabled only if survival does not drop and ideally
rises; a negative result flips the config default OFF and is recorded
honestly (docs/evidence/thief-certificate.md).

Run: uv run python scripts/measure_certificate.py [games_per_cop]
Output: results/experiments/thief_certificate.json
"""

import json
import random
import sys
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.peer.perception import Perception
from p2p_thief.shared.config import Config
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.endgame import CertifiedThiefBrain
from p2p_thief.strategy.thief_brain import CopForArena

RESULT_PATH = Path("results/experiments/thief_certificate.json")
DEFAULT_GAMES = 30  # per cop per arm; the 3-cop pool makes 90 games/arm
# blind_pursuit = the realistic league condition (both sides blind); the two
# full-information hunters are the harsher training ceiling.
COPS = {"blind_pursuit": CopForArena, "trap": TrapCop, "deep_trap": DeepTrapCop}
BLIND_COPS = {"blind_pursuit"}
ARM_PRIVATE = {"shipped": {"strategy": {"endgame": {"enabled": False}}},
               "certificate": {"strategy": {"endgame": {"enabled": True}}}}


def build_thief(arm: str, seed: int):
    """Same shipped class both arms - only the certificate gate differs."""
    return CertifiedThiefBrain(Role.THIEF, random.Random(seed + 500), ARM_PRIVATE[arm])


def play(seed: int, config: Config, arm: str, cop_name: str) -> dict:
    engine = GameEngine(config.grid_size, config.cop_start, config.thief_start,
                        config.rule_set())
    cop = COPS[cop_name](Role.POLICE, random.Random(seed))
    thief = build_thief(arm, seed)
    perception = Perception(Role.THIEF, config.grid_size)  # shipped pipeline
    cop_belief = BeliefMap(config.grid_size)  # a blind cop's picture of us
    while engine.outcome is Outcome.ONGOING:
        view = cop_belief if cop_name in BLIND_COPS else None
        action = cop.decide(engine, view)
        wall = tuple(action["cell"]) if action["type"] == "barrier" else None
        protocol.apply_action(engine, Role.POLICE, action)
        if engine.outcome is not Outcome.ONGOING:
            break
        # we read the cop PRE-boundary, exactly as the live peer does
        perception.observe(engine, Role.POLICE, None, barrier_cell=wall)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, perception.belief))
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
    certified = thief.certificate.certified
    return {"survived": engine.outcome is Outcome.SURVIVAL,
            "turns": engine.turns_completed, "certified": certified}


def run_arm(config: Config, arm: str, games: int) -> dict:
    per_cop, all_games = {}, []
    for cop_name in COPS:
        played = [play(seed, config, arm, cop_name) for seed in range(games)]
        per_cop[cop_name] = {
            "games": games,
            "survival_rate": round(sum(g["survived"] for g in played) / games, 3),
            "mean_turns_survived": round(sum(g["turns"] for g in played) / games, 2),
        }
        all_games.extend(played)
    return {"games": len(all_games),
            "survival_rate": round(
                sum(g["survived"] for g in all_games) / len(all_games), 3),
            "mean_turns_survived": round(
                sum(g["turns"] for g in all_games) / len(all_games), 2),
            "certified_turns": sum(g["certified"] for g in all_games),
            "per_cop": per_cop}


def main() -> None:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAMES
    config = Config.load("config")
    report = {"description": "blind thief survival with/without the certificate, "
                             "same seeds, 3-cop pool, shipped Perception pipeline",
              "games_per_cop_per_arm": games,
              "arms": {arm: run_arm(config, arm, games)
                       for arm in ("shipped", "certificate")}}
    report["survival_delta"] = round(
        report["arms"]["certificate"]["survival_rate"]
        - report["arms"]["shipped"]["survival_rate"], 3)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
