# PRD 08 — Deep-RL evasion: MLP Q-network vs the learned trap cop

## Description & theory

The linear evasion brain trained only against a movement cop; the twin
repo's Double-DQN cop proved barrier traps beat even perfect movement
evasion (0.74). `strategy/rl_deep.py` learns evasion against exactly that
threat: a small MLP (9 → tanh(12) → 1, hand-rolled backprop, pure Python —
rule 25) whose features track precisely what traps destroy — escape-route
count, reachable-region size, wall distance, barrier density, chase parity.
The adversary lives in `strategy/arena_cop.py`: the twin's TRAINED cop
replayed from copied weight DATA (`data/arena_cop_weights.json`) with
locally duplicated logic — the mirrored-twin rule forbids cross-repo
imports; static duplication and data files are the sanctioned mechanism.
Training (`scripts/train_deep_rl.py`) is Double-DQN with experience replay,
frozen target network, room/distance-shaped reward and best-eval
checkpointing. The thief's action space is moves+STAY only (barriers are
cop-only physics, ch. 3).

## I/O contracts

- `features(engine, move, cop=None) -> list[9 floats]` — pure after-move
  quantities; `cop` overrides the threat cell (belief argmax in blind games).
- `DeepQBrain(role, rng).decide(engine, belief=None) -> move action` — the
  standard brain seam; greedy at play time; repo-anchored weight loading.
- `arena_cop.TrapCop / DeepTrapCop` — sparring adversaries; every emitted
  action passes the engine's own validation.
- Artifacts: `results/experiments/deep_rl_training.json`,
  `deep_rl_training_v2_ensemble.json` (recorded collapse),
  `deep_rl_finetune.json` (knife-edge finding), `assets/deep_rl_curve*.png`.

## Measured performance (100 held-out games each)

| Policy vs the learned trap cop | Survival |
|---|---|
| Random-init net | 0.00 |
| Hand-coded ThiefBrain | 0.49 |
| **Deep v1 (shipped)** | **1.00** (also 1.00 vs cop v3) |
| v1 under radius-2 belief noise | **0.00** — the knife-edge |
| v2 from-scratch ensemble retrain | 0.06 (recorded collapse) |

The knife-edge finding is the mechanism's central claim: near-optimal
evasion RUNS ON exact opponent information — belief error is fatal, and
even lr-0.003 fine-tuning from the champion weights collapses the
specialist within ~100 episodes. This is the evidence-backed reason the
robust hand-coded ThiefBrain remains league default.

## Alternatives considered & rejected

- **torch/numpy** — rejected (dependency weight vs a 9×12 network).
- **Training vs a heuristic barrier cop only** — rejected after measurement:
  our scripted TrapCop was too weak to threaten anything (1.00 survival at
  episode 0); only the twin's learned cop provides real pressure.
- **Shipping the robust-trained generalist** — rejected by coded promotion
  gates, twice: the from-scratch ensemble collapsed (0.06) and the
  warm-start fine-tune never rose above 0.00 noisy while destroying the
  specialist. Specialist v1 ships; robustness lives in ThiefBrain.

## Success criteria (all met, tested)

- Legal moves only, both exploration and greedy modes (tests).
- MLP math verified (deterministic forward; SGD reduces error).
- The exact league config line loads through `resolve_brain` (seam test).
- The arena adversary is proven a genuine threat (captures a random walker —
  test), and every negative result is a committed artifact, not a footnote.
