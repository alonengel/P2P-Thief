"""Warm-start fine-tune: keep the v1 specialist, ADD robustness.

The from-scratch ensemble retraining collapsed (0.06, recorded). This is the
principled fix: initialize from the SHIPPED v1 weights (the 1.00 specialist
vs the learned trap cop) and fine-tune gently - low LR, low epsilon - on the
ensemble + belief-noise regime. Accept the result ONLY if it keeps >=0.95 vs
the learned trap cop while improving the robustness evals; otherwise v1
stays shipped (the gate is in code, not in judgment).
Run: uv run python scripts/finetune_deep_rl.py [episodes]
"""

import json
import random
import sys
from collections import deque
from pathlib import Path

import train_deep_rl as t

from p2p_thief.domain.primitives import Outcome, Role
from p2p_thief.strategy.arena_cop import TrapCop
from p2p_thief.strategy.rl_deep import WEIGHTS_PATH, DeepQBrain, Mlp

LR_FINE, EPS_HI, EPS_LO = 0.003, 0.2, 0.02


def robustness(net) -> dict:
    brain = DeepQBrain(Role.THIEF, random.Random(80_000), net=net)
    return {
        "vs_learned_trap_cop": t.evaluate(net, 90_000, 100),
        "vs_learned_trap_cop_noisy": t.evaluate(net, 93_000, 100, noisy=True),
        "vs_heuristic_trapcop": sum(
            t.run_episode(brain, 95_000 + i, cop_cls=TrapCop) is Outcome.SURVIVAL
            for i in range(100)) / 100,
    }


def main(episodes: int = 1500) -> None:
    net = Mlp(rng := random.Random(11))
    net.load_state(json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))["net"])
    baseline = robustness(net)
    print("v1 baseline:", {k: round(v, 2) for k, v in baseline.items()})
    target_net = t._clone(net)
    brain = DeepQBrain(Role.THIEF, rng, net=net)
    buffer: deque = deque(maxlen=t.BUFFER)
    saved_lr, t.LR = t.LR, LR_FINE  # gentle steps: fine-tuning, not relearning
    best_state, best_score = json.loads(json.dumps(net.state())), -1.0
    try:
        for episode in range(episodes):
            brain.epsilon = max(EPS_LO, EPS_HI * (1 - episode / (0.9 * episodes)))
            t.run_episode(brain, 30_000 + episode, buffer=buffer,
                          cop_cls=t.ENSEMBLE[episode % len(t.ENSEMBLE)], noisy=True)
            if len(buffer) >= t.BATCH:
                for _ in range(2):
                    t.replay_step(net, target_net, buffer, rng)
            if (episode + 1) % t.SYNC_EPISODES == 0:
                target_net = t._clone(net)
            if episode % 100 == 0 or episode == episodes - 1:
                spec = t.evaluate(net, 50_000, 25)
                noisy = t.evaluate(net, 51_000, 25, noisy=True)
                score = spec + noisy if spec >= 0.92 else -1.0  # specialist gate
                if score > best_score:
                    best_score = score
                    best_state = json.loads(json.dumps(net.state()))
                print(f"ep {episode:5d}  specialist={spec:.2f} noisy={noisy:.2f}")
    finally:
        t.LR = saved_lr
    net.load_state(best_state)
    tuned = robustness(net)
    print("fine-tuned:", {k: round(v, 2) for k, v in tuned.items()})
    keep = (tuned["vs_learned_trap_cop"] >= 0.95
            and tuned["vs_learned_trap_cop_noisy"] >= baseline["vs_learned_trap_cop_noisy"]
            and tuned["vs_heuristic_trapcop"] >= baseline["vs_heuristic_trapcop"])
    out = Path("results/experiments/deep_rl_finetune.json")
    out.write_text(json.dumps({
        "v1_baseline": baseline, "fine_tuned_best": tuned, "episodes": episodes,
        "lr": LR_FINE, "epsilon": [EPS_HI, EPS_LO], "games_per_eval": 100,
        "shipped": "fine-tuned" if keep else "v1 (gate not met)",
        "gate": ">=0.95 specialist AND no robustness regression",
    }, indent=2), encoding="utf-8")
    if keep:
        WEIGHTS_PATH.write_text(json.dumps(
            {"net": net.state(), "version": "v1.5-warmstart", "lr": LR_FINE,
             "episodes": episodes, "double_dqn": True}, indent=2), encoding="utf-8")
        print("SHIPPED: fine-tuned v1.5 (gate met)")
    else:
        print("KEPT v1: fine-tune failed the gate; experiment recorded")


if __name__ == "__main__":
    sys.path.insert(0, "scripts")
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
