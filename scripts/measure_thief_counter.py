"""Keep-gate A/B for the anti-freeze doctrine + belief-native forecast.

Arms (same seeds per cop): "old" = the previously shipped StealthThiefBrain;
"new" = DoctrineThiefBrain, all four knobs ON; plus leave-one-out ablations
(no_fresh_flee / no_stay_cap / no_pocket_escape / no_forecast) against the
hardest belief-led hunter only. The thief is always BLIND (scent + declared
walls feed its BeliefMap). Cop pool: AgedBeliefTrapCop (blind: aged-belief
pounce + surgical walls — the hunting pattern the counter-build targets),
CopForArena (blind pursuit), TrapCop and DeepTrapCop (full-information
ceilings). Keep rule per knob: default-ON only if removing it does not help.

Run: uv run python scripts/measure_thief_counter.py [games_per_cop]
Output: results/experiments/thief_counter.json
"""

import json
import random
import sys
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.shared.config import Config
from p2p_thief.strategy.arena_aged_cop import AgedBeliefTrapCop
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.doctrine import DEFAULTS, DoctrineThiefBrain
from p2p_thief.strategy.movement_deception import StealthThiefBrain
from p2p_thief.strategy.thief_brain import CopForArena

RESULT_PATH = Path("results/experiments/thief_counter.json")
DEFAULT_GAMES = 60
COPS = {"aged_trap": AgedBeliefTrapCop, "blind_pursuit": CopForArena,
        "trap": TrapCop, "deep_trap": DeepTrapCop}
BLIND_COPS = {"aged_trap", "blind_pursuit"}
KNOBS = ("fresh_flee", "stay_cap", "pocket_escape", "forecast")
# Leave-one-out arms face the belief-led hunter AND the wall-building
# full-information hunter: the second breaks 100%-survival ceilings.
ABLATION_COPS = ("aged_trap", "trap")


def build_thief(arm: str, seed: int):
    rng = random.Random(seed + 500)
    if arm == "old":
        return StealthThiefBrain(Role.THIEF, rng)
    doctrine = {**DEFAULTS, **dict.fromkeys(KNOBS, True)}
    if arm.startswith("no_"):
        doctrine[arm[3:]] = False
    return DoctrineThiefBrain(Role.THIEF, rng, doctrine=doctrine)


def play(seed: int, config: Config, arm: str, cop_name: str) -> dict:
    engine = GameEngine(config.grid_size, config.cop_start, config.thief_start,
                        config.rule_set())
    cop = COPS[cop_name](Role.POLICE, random.Random(seed))
    thief = build_thief(arm, seed)
    belief = BeliefMap(config.grid_size)      # the thief's picture of the cop
    cop_belief = BeliefMap(config.grid_size)  # a blind cop's picture of us
    while engine.outcome is Outcome.ONGOING:
        view = cop_belief if cop_name in BLIND_COPS else None
        action = cop.decide(engine, view)
        protocol.apply_action(engine, Role.POLICE, action)
        if engine.outcome is not Outcome.ONGOING:
            break
        belief.diffuse(engine.board)  # the thief's perception order
        if action["type"] == "barrier":
            belief.observe_barrier(tuple(action["cell"]), engine.board)
        belief.observe_scent(engine.scent[Role.POLICE], engine.board)
        protocol.apply_action(engine, Role.THIEF, thief.decide(engine, belief))
        cop_belief.diffuse(engine.board)
        cop_belief.observe_scent(engine.scent[Role.THIEF], engine.board)
    return {"survived": engine.outcome is Outcome.SURVIVAL,
            "turns": engine.turns_completed}


def run_arm(config: Config, arm: str, games: int, cops) -> dict:
    per_cop = {}
    for cop_name in cops:
        played = [play(seed, config, arm, cop_name) for seed in range(games)]
        per_cop[cop_name] = {
            "games": games,
            "survival_rate": round(sum(g["survived"] for g in played) / games, 3),
            "mean_turns_survived": round(sum(g["turns"] for g in played) / games, 2),
        }
    return per_cop


def main() -> None:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAMES
    config = Config.load("config")
    arms = {"old": run_arm(config, "old", games, COPS),
            "new": run_arm(config, "new", games, COPS)}
    for knob in KNOBS:
        arms[f"no_{knob}"] = run_arm(config, f"no_{knob}", games, ABLATION_COPS)
    keep_gates = {}
    for knob in KNOBS:
        deltas = {
            cop: round(arms["new"][cop]["survival_rate"]
                       - arms[f"no_{knob}"][cop]["survival_rate"], 3)
            for cop in ABLATION_COPS
        }
        keep_gates[knob] = {  # pays somewhere, hurts nowhere -> stays ON
            "delta_by_cop": deltas,
            "keep_on": all(d >= 0 for d in deltas.values())
            and any(d > 0 for d in deltas.values()),
        }
    regressions = {
        cop: round(arms["new"][cop]["survival_rate"]
                   - arms["old"][cop]["survival_rate"], 3)
        for cop in COPS
    }
    report = {
        "description": "blind thief survival, old (stealth) vs new (doctrine) "
                       "arms on shared seeds; leave-one-out knob ablations vs "
                       "the aged-belief hunter; keep rule: ON only if removing "
                       "the knob does not help",
        "games_per_cop_per_arm": games,
        "arms": arms,
        "keep_gates": keep_gates,
        "survival_delta_new_minus_old": regressions,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
