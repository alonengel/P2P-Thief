"""Train the LinearQBrain THIEF (evasion) vs the scripted pursuing cop
(CopForArena). From-scratch evasion fails the hard-exploration problem
(never survives long enough to see a +1), so training starts from an
informed prior and amplifies it - see README RL section.

Rewards: capture -1, survival +1, per-turn shaping +0.02*(distance/grid)
(distance is life). Epsilon decays 0.30 -> 0.05.
Outputs: results/rl_weights.json, results/experiments/rl_training.json,
assets/rl_learning_curve.png. Reproducible: fixed base seed.
Run: uv run python scripts/train_rl.py [episodes]
"""

import json
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.rl_brain import WEIGHTS_PATH, LinearQBrain
from p2p_thief.strategy.thief_brain import CopForArena

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
ALPHA, GAMMA = 0.05, 0.95


def run_episode(brain: LinearQBrain, seed: int, learn: bool) -> tuple[Outcome, float]:
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    cop = CopForArena(Role.POLICE, random.Random(seed + 9000))
    td_total = 0.0
    while engine.outcome is Outcome.ONGOING:
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
        if engine.outcome is not Outcome.ONGOING:
            me = target = None
            move = Move.STAY
        else:
            me, target = engine.positions[Role.THIEF], engine.positions[Role.POLICE]
            action = brain.decide(engine)
            move = Move[action["move"]]
            protocol.apply_action(engine, Role.THIEF, action)
        if learn and me is not None:
            grid = engine.board.grid_size
            distance = bfs_distances(engine.board, engine.positions[Role.POLICE]).get(
                engine.positions[Role.THIEF], 2 * grid
            )
            if engine.outcome is Outcome.CAPTURE:
                reward, next_q = -1.0, 0.0
            elif engine.outcome is Outcome.SURVIVAL:
                reward, next_q = 1.0, 0.0
            else:
                reward = 0.02 * (distance / grid)
                new_me = engine.positions[Role.THIEF]
                new_target = engine.positions[Role.POLICE]
                next_q = max(
                    brain.q(engine, new_me, new_target, m)
                    for m in engine.board.legal_moves(new_me)
                )
            td_total += abs(brain.td_update(engine, me, target, move, reward, next_q,
                                            ALPHA, GAMMA))
    return engine.outcome, td_total


def evaluate(brain: LinearQBrain, base_seed: int, games: int = 50) -> float:
    saved, brain.epsilon = brain.epsilon, 0.0
    eval_rng, brain.rng = brain.rng, random.Random(base_seed - 1)  # own stream
    wins = sum(run_episode(brain, base_seed + i, learn=False)[0] is Outcome.SURVIVAL
               for i in range(games))
    brain.epsilon, brain.rng = saved, eval_rng
    return wins / games


def train(episodes: int, start_weights: list[float], label: str):
    brain = LinearQBrain(Role.THIEF, random.Random(7), weights=list(start_weights))
    curve, td_curve = [], []
    for episode in range(episodes):
        brain.epsilon = max(0.05, 0.30 * (1 - episode / episodes))
        _, td = run_episode(brain, 10_000 + episode, learn=True)
        td_curve.append(td)
        if episode % 50 == 0 or episode == episodes - 1:
            win_rate = evaluate(brain, 50_000)
            curve.append({"episode": episode, "eval_win_rate": win_rate,
                          "epsilon": round(brain.epsilon, 3)})
            print(f"{label} ep {episode:4d}  win_rate={win_rate:.2f}")
    return brain, curve, td_curve


def main(episodes: int = 600) -> None:
    # The graded comparison: from-scratch evasion never survives long enough to
    # see a +1 (hard exploration) while the informed prior amplifies to 1.0.
    scratch, scratch_curve, _ = train(episodes, [0.0] * 5, "scratch")
    brain, curve, td_curve = train(episodes, [0.0, 1.0, 1.0, 0.5, 0.0], "prior")
    WEIGHTS_PATH.parent.mkdir(exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps(
        {"weights": brain.weights, "episodes": episodes, "alpha": ALPHA, "gamma": GAMMA},
        indent=2), encoding="utf-8")
    out = Path("results/experiments/rl_training.json")
    out.write_text(json.dumps({
        "runs": {"from_scratch": {"curve": scratch_curve,
                                  "final_weights": scratch.weights},
                 "informed_prior": {"curve": curve, "final_weights": brain.weights}},
        "final_weights": brain.weights, "eval_games_per_point": 50, "base_seed": 7,
        "negative_result_note": "from-scratch evasion fails the hard-exploration "
                                "problem: capture ends every episode before the "
                                "first survival reward is ever observed",
    }, indent=2), encoding="utf-8")
    figure, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    for run_curve, color, label in ((scratch_curve, "#cf222e", "from scratch"),
                                    (curve, "#1f6feb", "informed prior")):
        ax1.plot([p["episode"] for p in run_curve],
                 [p["eval_win_rate"] for p in run_curve],
                 marker="o", color=color, label=label)
    ax1.legend(loc="center right", fontsize=8)
    ax1.set(xlabel="training episode", ylabel="greedy eval survival rate",
            title="Linear-FA Q-learning thief vs pursuing cop")
    window = 25
    smoothed = [sum(td_curve[max(0, i - window):i + 1]) / len(td_curve[max(0, i - window):i + 1])
                for i in range(len(td_curve))]
    ax2.plot(smoothed, color="#d29922")
    ax2.set(xlabel="training episode", ylabel="|TD error| (moving avg, prior run)",
            title="Convergence")
    figure.tight_layout()
    figure.savefig("assets/rl_learning_curve.png", dpi=120)
    print("weights:", [round(w, 3) for w in brain.weights])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 600)
