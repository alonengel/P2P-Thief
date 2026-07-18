"""Double-DQN evasion training vs the twin's LEARNED barrier-trap cop.

The linear evasion brain only ever faced a movement cop; the twin repo's
Double-DQN cop captures even a perfect movement-evader 0.74 by trapping.
This trains the MLP thief against exactly that adversary (DeepTrapCop -
replayed from copied weight data, see strategy/arena_cop.py), with the
heuristic TrapCop as a secondary benchmark. Experience replay + frozen
target + best-eval checkpoint.
Outputs: results/deep_rl_weights.json, results/experiments/deep_rl_training.json,
assets/deep_rl_curve.png. Run: uv run python scripts/train_deep_rl.py [episodes]
"""

import json
import random
import sys
from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.arena_cop import DeepTrapCop
from p2p_thief.strategy.rl_deep import WEIGHTS_PATH, DeepQBrain, Mlp, features
from p2p_thief.strategy.thief_brain import ThiefBrain

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
GAMMA, LR, BATCH, SYNC_EPISODES, BUFFER = 0.97, 0.01, 32, 10, 5000


def run_episode(brain, seed: int, buffer=None, thief_cls=None):
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    cop = DeepTrapCop(Role.POLICE, random.Random(seed + 9000))
    actor = thief_cls(Role.THIEF, random.Random(seed + 7000)) if thief_cls else brain
    while engine.outcome is Outcome.ONGOING:
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
        if engine.outcome is not Outcome.ONGOING:
            phi = None
        else:
            action = actor.decide(engine)
            phi = features(engine, Move[action["move"]]) if buffer is not None else None
            protocol.apply_action(engine, Role.THIEF, action)
        if buffer is None:
            continue
        grid = engine.board.grid_size
        if engine.outcome is Outcome.CAPTURE:
            reward, next_phis = -1.0, []
        elif engine.outcome is not Outcome.ONGOING:
            reward, next_phis = 1.0, []
        else:
            me = engine.positions[Role.THIEF]
            d = bfs_distances(engine.board, engine.positions[Role.POLICE]).get(me, 0)
            room = len(bfs_distances(engine.board, me))
            reward = 0.02 * (d / grid) + 0.05 * (room / (grid * grid))
            next_phis = [features(engine, m) for m in engine.board.legal_moves(me)]
        if phi is not None:
            buffer.append((phi, reward, next_phis))
    return engine.outcome


def replay_step(net, target_net, buffer, rng) -> None:
    for phi, reward, next_phis in rng.sample(list(buffer), k=min(BATCH, len(buffer))):
        if next_phis:  # Double-DQN: online selects, frozen evaluates
            best = max(next_phis, key=lambda p: net.forward(p)[0])
            target = reward + GAMMA * target_net.forward(best)[0]
        else:
            target = reward
        q, hidden = net.forward(phi)
        net.sgd(phi, hidden, target - q, LR)


def _clone(net: Mlp) -> Mlp:
    frozen = Mlp(random.Random(8))
    frozen.load_state(json.loads(json.dumps(net.state())))
    return frozen


def evaluate(net, base_seed: int, games: int) -> float:
    brain = DeepQBrain(Role.THIEF, random.Random(base_seed - 1), net=net)
    wins = sum(run_episode(brain, base_seed + i) is Outcome.SURVIVAL
               for i in range(games))
    return wins / games


def benchmark(thief_cls, games: int = 100) -> float:
    return sum(run_episode(None, 90_000 + i, thief_cls=thief_cls)
               is Outcome.SURVIVAL for i in range(games)) / games


def main(episodes: int = 4000) -> None:
    rng = random.Random(7)
    net = Mlp(rng)
    target_net = _clone(net)
    brain = DeepQBrain(Role.THIEF, rng, net=net)
    buffer: deque = deque(maxlen=BUFFER)
    curve, best_eval, best_state = [], -1.0, net.state()
    for episode in range(episodes):
        brain.epsilon = max(0.05, 1.0 * (1 - episode / (0.9 * episodes)))
        run_episode(brain, 10_000 + episode, buffer=buffer)
        if len(buffer) >= BATCH:
            for _ in range(4):
                replay_step(net, target_net, buffer, rng)
        if (episode + 1) % SYNC_EPISODES == 0:
            target_net = _clone(net)
        if episode % 100 == 0 or episode == episodes - 1:
            survival = evaluate(net, 50_000, 25)
            if survival > best_eval:
                best_eval, best_state = survival, json.loads(json.dumps(net.state()))
            curve.append({"episode": episode, "survival_vs_deep_cop": survival,
                          "epsilon": round(brain.epsilon, 3)})
            print(f"ep {episode:5d}  survival_vs_deep_cop={survival:.2f}")
    net.load_state(best_state)
    final = evaluate(net, 90_000, 100)
    hand = benchmark(ThiefBrain)
    print(f"FINAL: deep thief {final:.2f} | hand-coded ThiefBrain {hand:.2f}")
    WEIGHTS_PATH.write_text(json.dumps(
        {"net": net.state(), "episodes": episodes, "gamma": GAMMA, "lr": LR,
         "double_dqn": True, "checkpoint": "best-eval"}, indent=2), encoding="utf-8")
    Path("results/experiments/deep_rl_training.json").write_text(json.dumps({
        "curve": curve, "base_seed": 7, "eval_games_per_point": 25,
        "adversary": "DeepTrapCop - the twin's trained Double-DQN barrier cop "
                     "(0.74 capture vs a perfect movement evader), replayed "
                     "from copied weight data",
        "final_survival_vs_deep_cop": {"win_rate": final, "games": 100},
        "hand_coded_thiefbrain_benchmark": {"win_rate": hand, "games": 100},
        "note": "the linear evasion brain never trained against barriers",
    }, indent=2), encoding="utf-8")
    figure, ax = plt.subplots(figsize=(7, 4))
    ax.plot([p["episode"] for p in curve], [p["survival_vs_deep_cop"] for p in curve],
            marker="o", color="#1f6feb", label="deep thief vs learned trap cop")
    ax.axhline(hand, color="#2ea043", linestyle="--",
               label=f"hand-coded ThiefBrain ({hand:.2f})")
    ax.legend(fontsize=8)
    ax.set(xlabel="training episode", ylabel="greedy survival rate",
           title="Double-DQN thief vs the twin's learned barrier cop")
    figure.tight_layout()
    figure.savefig("assets/deep_rl_curve.png", dpi=120)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
