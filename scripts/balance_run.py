"""Wire-shape balance, thief side: how much does OUR evasion lose when blinded?

Decomposes the wire-shape question per role: every thief brain runs under two
information arms - exact (bookletter: rival cell as revealed) and lag-1 (the
best-case hidden-play scent reading: rival's cell one move stale) - against
FULL-STRENGTH arena trap cops (which always see truly; adversary held at max).
Deterministic, regenerable; companion table lives in the police repo (cop
side). Output: results/experiments/wire_shape_balance.json.
Run: uv run python scripts/balance_run.py [games_per_cell]
"""

import json
import random
import sys
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.rl_deep import DeepQBrain
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
COPS = (("TrapCop", TrapCop), ("DeepTrapCop", DeepTrapCop))
EVADERS = (("ThiefBrain", ThiefBrain), ("DeepQBrain", DeepQBrain))
ARMS = ("exact", "lag1")


def run(cop, thief, seed: int, arm: str) -> Outcome:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    while engine.outcome is Outcome.ONGOING:
        cop_prev = engine.positions[Role.POLICE]
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
        if engine.outcome is Outcome.ONGOING:
            if arm == "exact":
                action = thief.decide(engine)  # true full-info path
            else:
                shim = type("T", (), {"argmax_cell": lambda self, c=cop_prev: c})()
                action = thief.decide(engine, belief=shim)
            protocol.apply_action(engine, Role.THIEF, action)
    return engine.outcome


def main(games: int = 32) -> None:
    table = {}
    for cop_name, cop_cls in COPS:
        for evader_name, evader_cls in EVADERS:
            for arm in ARMS:
                wins = 0
                for i in range(games):
                    cop = cop_cls(Role.POLICE, random.Random(70_000 + i))
                    thief = evader_cls(Role.THIEF, random.Random(80_000 + i))
                    wins += run(cop, thief, 70_000 + i, arm) is Outcome.SURVIVAL
                table[f"{cop_name} vs {evader_name} [{arm}]"] = wins / games
                print(f"{cop_name:>11} vs {evader_name:<13} [{arm:>5}]: "
                      f"survival {wins}/{games}", flush=True)
    out = Path("results/experiments/wire_shape_balance.json")
    out.write_text(json.dumps({
        "side": "thief (this repo); cop side in the twin repo",
        "games_per_cell": games, "base_seed": 70_000,
        "arms": {"exact": "rival cell as revealed (bookletter lock)",
                 "lag1": "rival cell one move stale - best-case hidden-play "
                         "scent reading; adversary always fully informed"},
        "table": table,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 32)
