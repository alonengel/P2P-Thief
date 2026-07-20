"""Gated attempt: a LAG-1-NATIVE deep evader for hidden-shape play.

The balance table exposed the one information-sensitive cell in our roster:
vs the learned trap cop, thief survival collapses 32/32 (exact) -> 5/32
(lag-1). The jitter-trained attempt collapsed (recorded); THIS one trains on
the actual hidden-play signal - the cop's cell one move stale - vs the trap
cop ensemble. Separate weights file: the shipped exact-mode v1 is never
touched. Gate: beat the hand brain's lag-1 survival vs DeepTrapCop (0.12)
by a real margin (>=0.30) without losing TrapCop lag-1 (>=0.90); else the
attempt is recorded and nothing ships.
Run: uv run python scripts/train_deep_rl_hidden.py [episodes]
"""

import json
import random
import sys
from collections import deque
from pathlib import Path

import train_deep_rl as t

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import bfs_distances
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop
from p2p_thief.strategy.rl_deep import REPO_ROOT, DeepQBrain, Mlp, features

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
HIDDEN_WEIGHTS = REPO_ROOT / "results" / "deep_rl_weights_hidden.json"
ENSEMBLE = (DeepTrapCop, TrapCop)


def run_lag1(brain, seed: int, buffer=None, cop_cls=DeepTrapCop):
    engine = GameEngine(7, (0, 0), (3, 3), RULES)
    cop = cop_cls(Role.POLICE, random.Random(seed + 9000))
    while engine.outcome is Outcome.ONGOING:
        cop_prev = engine.positions[Role.POLICE]
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
        if engine.outcome is not Outcome.ONGOING:
            phi = None
        else:
            action = brain.decide(
                engine, belief=type("T", (), {"argmax_cell": lambda s, c=cop_prev: c})())
            phi = (features(engine, Move[action["move"]], cop=cop_prev)
                   if buffer is not None else None)
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
            lagged = engine.positions[Role.POLICE]  # next decision's lag-1 view
            next_phis = [features(engine, m, cop=lagged)
                         for m in engine.board.legal_moves(me)]
        if phi is not None:
            buffer.append((phi, reward, next_phis))
    return engine.outcome


def survival(net, base_seed: int, games: int, cop_cls) -> float:
    brain = DeepQBrain(Role.THIEF, random.Random(base_seed - 1), net=net)
    return sum(run_lag1(brain, base_seed + i, cop_cls=cop_cls) is Outcome.SURVIVAL
               for i in range(games)) / games


def main(episodes: int = 4000) -> None:
    net = Mlp(rng := random.Random(13))
    target_net = t._clone(net)
    brain = DeepQBrain(Role.THIEF, rng, net=net)
    buffer: deque = deque(maxlen=t.BUFFER)
    best_eval, best_state = -1.0, net.state()
    curve = []
    for episode in range(episodes):
        brain.epsilon = max(0.05, 1.0 * (1 - episode / (0.9 * episodes)))
        run_lag1(brain, 10_000 + episode, buffer=buffer,
                 cop_cls=ENSEMBLE[episode % len(ENSEMBLE)])
        if len(buffer) >= t.BATCH:
            for _ in range(4):
                t.replay_step(net, target_net, buffer, rng)
        if (episode + 1) % t.SYNC_EPISODES == 0:
            target_net = t._clone(net)
        if episode % 100 == 0 or episode == episodes - 1:
            deep = survival(net, 50_000, 25, DeepTrapCop)
            if deep > best_eval:
                best_eval, best_state = deep, json.loads(json.dumps(net.state()))
            curve.append({"episode": episode, "survival_lag1_vs_deep_cop": deep})
            print(f"ep {episode:5d}  lag1_vs_deep_cop={deep:.2f}", flush=True)
    net.load_state(best_state)
    finals = {"lag1_vs_deep_cop": survival(net, 90_000, 100, DeepTrapCop),
              "lag1_vs_trapcop": survival(net, 93_000, 100, TrapCop)}
    gate = finals["lag1_vs_deep_cop"] >= 0.30 and finals["lag1_vs_trapcop"] >= 0.90
    print(f"FINAL: {finals}  gate={'PASS' if gate else 'FAIL'}")
    Path("results/experiments/deep_rl_hidden_training.json").write_text(json.dumps({
        "curve": curve, "final_100_game_evals": finals, "base_seed": 13,
        "gate": "lag1 vs DeepTrapCop >= 0.30 AND vs TrapCop >= 0.90 "
                "(hand brain baselines: 0.12 / 1.00)",
        "shipped": bool(gate),
        "note": "lag-1-NATIVE training (structured stale info, not jitter); "
                "exact-mode v1 weights untouched either way",
    }, indent=2) + "\n", encoding="utf-8")
    if gate:
        HIDDEN_WEIGHTS.write_text(json.dumps(
            {"net": net.state(), "episodes": episodes, "mode": "lag1-native",
             "double_dqn": True, "checkpoint": "best-eval"}, indent=2),
            encoding="utf-8")
        print("SHIPPED separate hidden-mode weights")
    else:
        print("KEPT: nothing ships; attempt recorded")


if __name__ == "__main__":
    sys.path.insert(0, "scripts")
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
